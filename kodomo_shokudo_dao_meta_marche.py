#!/usr/bin/env python3
"""子ども食堂DAO × Metaマルシェ 地方創生AX オフラインプロトタイプ。

外部依存なし（Python 3.10+ 標準ライブラリのみ）。
World ID とガバメントAI「源内」は実APIを呼ばず、差し替え可能なスタブとして実装する。

本ファイルは政策決定・調達適合・セキュリティ認証の代替ではない。
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


ISO = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(ISO)


def sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class VerificationMethod(str, Enum):
    """本人確認の段階。行政実証では既存公的確認を既定にし、World ID は選択肢とする。"""

    PUBLIC_CREDENTIAL = "public_credential"  # 公的個人認証等を想定したプレースホルダ
    WORLD_ID_ORB = "world_id_orb"
    WORLD_ID_DEVICE = "world_id_device"
    DEMO_MOCK = "demo_mock"


class LedgerEventType(str, Enum):
    INFLOW = "inflow"
    EXPENDITURE = "expenditure"
    PROCUREMENT = "procurement"
    GRANT = "grant"
    MARCHE_REBATE = "marche_rebate"


@dataclass(frozen=True)
class IdentityProof:
    method: VerificationMethod
    action: str
    nullifier_hash: str
    signal_hash: str
    verified_at: str
    extra: dict[str, Any] = field(default_factory=dict)


class WorldIDVerifier:
    """World ID Developer Portal `/api/v2/verify/{app_id}` への差し替え口。

    既定はオフライン・デモ用モック。実運用では verify() 内を HTTP 検証に置換する。
    モックは「同一 (action, person_secret) → 同一 nullifier」を再現し、二重登録検知を示す。
    """

    def __init__(self, app_id: str = "app_demo_offline", live: bool = False) -> None:
        self.app_id = app_id
        self.live = live

    def verify(
        self,
        *,
        person_secret: str,
        action: str,
        signal: str,
        verification_level: VerificationMethod = VerificationMethod.WORLD_ID_ORB,
    ) -> IdentityProof:
        if self.live:
            raise NotImplementedError(
                "実運用では World ID Cloud API の検証結果を IdentityProof に写像すること。"
                "本プロトタイプはオフライン・デモ専用。"
            )
        if verification_level not in {
            VerificationMethod.WORLD_ID_ORB,
            VerificationMethod.WORLD_ID_DEVICE,
            VerificationMethod.DEMO_MOCK,
        }:
            raise ValueError("WorldIDVerifier は World ID 系の verification_level のみを扱う")

        nullifier = sha256_hex(f"{self.app_id}|{action}|{person_secret}")
        return IdentityProof(
            method=verification_level,
            action=action,
            nullifier_hash=nullifier,
            signal_hash=sha256_hex(signal),
            verified_at=utc_now(),
            extra={"app_id": self.app_id, "mock": True},
        )


class PublicCredentialVerifier:
    """マイナンバーカード等の公的確認を想定したプレースホルダ。

    実証では JPKI / 既存窓口 KYC の結果ハッシュだけを受け取る想定。
    個人を特定する属性は保持しない。
    """

    def verify(self, *, subject_secret: str, action: str, signal: str) -> IdentityProof:
        nullifier = sha256_hex(f"jpki-placeholder|{action}|{subject_secret}")
        return IdentityProof(
            method=VerificationMethod.PUBLIC_CREDENTIAL,
            action=action,
            nullifier_hash=nullifier,
            signal_hash=sha256_hex(signal),
            verified_at=utc_now(),
            extra={"placeholder": True},
        )


class GennaiAIAssistant:
    """ガバメントAI「源内」連携スタブ。

    源内の実エンドポイント・認証・取扱区分（機密性2等）には接続しない。
    自治体が源内を恒常利用できる制度が整った場合の、プロンプト入出力の形だけを示す。
    """

    def summarize_proposal(self, title: str, body: str) -> str:
        clipped = body.replace("\n", " ").strip()
        if len(clipped) > 180:
            clipped = clipped[:177] + "..."
        return f"【源内スタブ要約】{title}: {clipped}"

    def vendor_copy(self, vendor_name: str, produce: str) -> str:
        return (
            f"【源内スタブ文案】{vendor_name}の{produce}。"
            "地域循環と子ども食堂への還元を一文で伝える（生成結果は職員確認が必須）。"
        )


@dataclass
class Vendor:
    vendor_id: str
    name: str
    produce: str
    identity: IdentityProof


@dataclass
class Sale:
    sale_id: str
    vendor_id: str
    amount_jpy: int
    rebate_to_shokudo_jpy: int
    created_at: str


@dataclass
class KodomoShokudo:
    shokudo_id: str
    name: str
    operator_identity: IdentityProof
    meals_estimate_yen_per_meal: int = 400


@dataclass
class LedgerRecord:
    seq: int
    event_type: LedgerEventType
    amount_jpy: int
    shokudo_id: str
    actor_nullifier: str
    note: str
    receipt_reference: str | None
    prev_hash: str
    record_hash: str
    created_at: str

    def to_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_type"] = self.event_type.value
        return data


class DuplicateNullifierError(ValueError):
    pass


class DuplicateReceiptError(ValueError):
    pass


class ChainIntegrityError(ValueError):
    pass


class AuditLedger:
    """個人情報を持たず、nullifier と領収書番号だけで追跡するハッシュチェーン台帳。"""

    def __init__(self) -> None:
        self._records: list[LedgerRecord] = []
        self._receipts: set[str] = set()

    def __len__(self) -> int:
        return len(self._records)

    def _next_hash(self, payload: dict[str, Any], prev_hash: str) -> str:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256_hex(f"{prev_hash}|{canonical}")

    def append(
        self,
        *,
        event_type: LedgerEventType,
        amount_jpy: int,
        shokudo_id: str,
        actor_nullifier: str,
        note: str,
        receipt_reference: str | None = None,
    ) -> LedgerRecord:
        if amount_jpy <= 0:
            raise ValueError("amount_jpy は正の整数である必要がある")
        if receipt_reference:
            if receipt_reference in self._receipts:
                raise DuplicateReceiptError(f"領収書番号の二重請求: {receipt_reference}")
            self._receipts.add(receipt_reference)

        prev_hash = self._records[-1].record_hash if self._records else "genesis"
        payload = {
            "seq": len(self._records) + 1,
            "event_type": event_type.value,
            "amount_jpy": amount_jpy,
            "shokudo_id": shokudo_id,
            "actor_nullifier": actor_nullifier,
            "note": note,
            "receipt_reference": receipt_reference,
            "created_at": utc_now(),
        }
        record = LedgerRecord(
            seq=payload["seq"],
            event_type=event_type,
            amount_jpy=amount_jpy,
            shokudo_id=shokudo_id,
            actor_nullifier=actor_nullifier,
            note=note,
            receipt_reference=receipt_reference,
            prev_hash=prev_hash,
            record_hash=self._next_hash(payload, prev_hash),
            created_at=payload["created_at"],
        )
        self._records.append(record)
        return record

    def verify_chain_integrity(self) -> bool:
        prev = "genesis"
        for rec in self._records:
            if rec.prev_hash != prev:
                raise ChainIntegrityError(f"seq={rec.seq} の prev_hash が一致しない")
            payload = {
                "seq": rec.seq,
                "event_type": rec.event_type.value,
                "amount_jpy": rec.amount_jpy,
                "shokudo_id": rec.shokudo_id,
                "actor_nullifier": rec.actor_nullifier,
                "note": rec.note,
                "receipt_reference": rec.receipt_reference,
                "created_at": rec.created_at,
            }
            expected = self._next_hash(payload, prev)
            if expected != rec.record_hash:
                raise ChainIntegrityError(f"seq={rec.seq} の record_hash が再計算と一致しない")
            prev = rec.record_hash
        return True

    def totals(self, shokudo_id: str | None = None) -> dict[str, int]:
        inflow = 0
        outflow = 0
        for rec in self._records:
            if shokudo_id and rec.shokudo_id != shokudo_id:
                continue
            if rec.event_type in {
                LedgerEventType.INFLOW,
                LedgerEventType.GRANT,
                LedgerEventType.MARCHE_REBATE,
            }:
                inflow += rec.amount_jpy
            else:
                outflow += rec.amount_jpy
        return {"inflow_jpy": inflow, "outflow_jpy": outflow, "balance_jpy": inflow - outflow}

    def export_records(self) -> list[dict[str, Any]]:
        return [r.to_public_dict() for r in self._records]


class DAOGovernance:
    """一人一票。同一 action の nullifier 再投票は拒否する。"""

    def __init__(self) -> None:
        self._votes: dict[str, dict[str, str]] = {}

    def vote(self, *, proposal_id: str, choice: str, identity: IdentityProof) -> None:
        if identity.action != f"dao_vote:{proposal_id}":
            raise ValueError("投票用 IdentityProof の action が提案と一致しない")
        bucket = self._votes.setdefault(proposal_id, {})
        if identity.nullifier_hash in bucket:
            raise DuplicateNullifierError("同一人物による二重投票")
        bucket[identity.nullifier_hash] = choice

    def tally(self, proposal_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for choice in self._votes.get(proposal_id, {}).values():
            counts[choice] = counts.get(choice, 0) + 1
        return counts


class KodomoShokudoMetaMarcheEcosystem:
    OPERATOR_ACTION = "shokudo_operator_kyc"
    VENDOR_ACTION = "marche_vendor_kyc"
    EXPENDITURE_ACTION = "shokudo_expenditure"

    def __init__(
        self,
        *,
        identity_backend: str = "world_id_mock",
        meals_yen_per_meal: int = 400,
    ) -> None:
        self.identity_backend = identity_backend
        self.world_id = WorldIDVerifier()
        self.public_id = PublicCredentialVerifier()
        self.gennai = GennaiAIAssistant()
        self.ledger = AuditLedger()
        self.dao = DAOGovernance()
        self.shokudos: dict[str, KodomoShokudo] = {}
        self.vendors: dict[str, Vendor] = {}
        self.sales: list[Sale] = []
        self.meals_yen_per_meal = meals_yen_per_meal
        self._operator_nullifiers: set[str] = set()
        self._vendor_nullifiers: set[str] = set()

    def _issue_identity(self, *, secret: str, action: str, signal: str) -> IdentityProof:
        if self.identity_backend == "public_credential":
            return self.public_id.verify(subject_secret=secret, action=action, signal=signal)
        level = (
            VerificationMethod.WORLD_ID_ORB
            if self.identity_backend == "world_id_mock"
            else VerificationMethod.DEMO_MOCK
        )
        return self.world_id.verify(
            person_secret=secret,
            action=action,
            signal=signal,
            verification_level=level,
        )

    def register_shokudo(self, *, name: str, operator_secret: str) -> KodomoShokudo:
        identity = self._issue_identity(
            secret=operator_secret,
            action=self.OPERATOR_ACTION,
            signal=name,
        )
        if identity.nullifier_hash in self._operator_nullifiers:
            raise DuplicateNullifierError("同一人物による子ども食堂の多重登録")
        self._operator_nullifiers.add(identity.nullifier_hash)
        shokudo = KodomoShokudo(
            shokudo_id=f"ks_{secrets.token_hex(4)}",
            name=name,
            operator_identity=identity,
            meals_estimate_yen_per_meal=self.meals_yen_per_meal,
        )
        self.shokudos[shokudo.shokudo_id] = shokudo
        return shokudo

    def register_vendor(self, *, name: str, produce: str, vendor_secret: str) -> Vendor:
        identity = self._issue_identity(
            secret=vendor_secret,
            action=self.VENDOR_ACTION,
            signal=name,
        )
        if identity.nullifier_hash in self._vendor_nullifiers:
            raise DuplicateNullifierError("同一人物による出店者の多重登録")
        self._vendor_nullifiers.add(identity.nullifier_hash)
        vendor = Vendor(
            vendor_id=f"vd_{secrets.token_hex(4)}",
            name=name,
            produce=produce,
            identity=identity,
        )
        self.vendors[vendor.vendor_id] = vendor
        return vendor

    def record_grant(self, *, shokudo_id: str, amount_jpy: int, note: str) -> LedgerRecord:
        shokudo = self.shokudos[shokudo_id]
        return self.ledger.append(
            event_type=LedgerEventType.GRANT,
            amount_jpy=amount_jpy,
            shokudo_id=shokudo_id,
            actor_nullifier=shokudo.operator_identity.nullifier_hash,
            note=note,
        )

    def record_donation(self, *, shokudo_id: str, amount_jpy: int, donor_nullifier: str, note: str) -> LedgerRecord:
        if shokudo_id not in self.shokudos:
            raise KeyError(shokudo_id)
        return self.ledger.append(
            event_type=LedgerEventType.INFLOW,
            amount_jpy=amount_jpy,
            shokudo_id=shokudo_id,
            actor_nullifier=donor_nullifier,
            note=note,
        )

    def record_expenditure(
        self,
        *,
        shokudo_id: str,
        operator_secret: str,
        amount_jpy: int,
        note: str,
        receipt_reference: str,
    ) -> LedgerRecord:
        shokudo = self.shokudos[shokudo_id]
        reauth = self._issue_identity(
            secret=operator_secret,
            action=self.EXPENDITURE_ACTION,
            signal=f"{shokudo_id}|{receipt_reference}",
        )
        expected = self._issue_identity(
            secret=operator_secret,
            action=self.OPERATOR_ACTION,
            signal=shokudo.name,
        )
        if expected.nullifier_hash != shokudo.operator_identity.nullifier_hash:
            raise PermissionError("支出報告の再認証が登録時の運営者と一致しない")
        return self.ledger.append(
            event_type=LedgerEventType.EXPENDITURE,
            amount_jpy=amount_jpy,
            shokudo_id=shokudo_id,
            actor_nullifier=reauth.nullifier_hash,
            note=note,
            receipt_reference=receipt_reference,
        )

    def record_sale_with_rebate(
        self,
        *,
        vendor_id: str,
        shokudo_id: str,
        amount_jpy: int,
        rebate_rate: float = 0.1,
    ) -> tuple[Sale, LedgerRecord]:
        if vendor_id not in self.vendors:
            raise KeyError(vendor_id)
        rebate = max(1, int(amount_jpy * rebate_rate))
        sale = Sale(
            sale_id=f"sl_{secrets.token_hex(4)}",
            vendor_id=vendor_id,
            amount_jpy=amount_jpy,
            rebate_to_shokudo_jpy=rebate,
            created_at=utc_now(),
        )
        self.sales.append(sale)
        record = self.ledger.append(
            event_type=LedgerEventType.MARCHE_REBATE,
            amount_jpy=rebate,
            shokudo_id=shokudo_id,
            actor_nullifier=self.vendors[vendor_id].identity.nullifier_hash,
            note=f"マルシェ売上還元 sale={sale.sale_id}",
        )
        return sale, record

    def dao_vote(self, *, proposal_id: str, choice: str, person_secret: str) -> None:
        identity = self._issue_identity(
            secret=person_secret,
            action=f"dao_vote:{proposal_id}",
            signal=choice,
        )
        self.dao.vote(proposal_id=proposal_id, choice=choice, identity=identity)

    def export_audit_report(self, shokudo_id: str) -> dict[str, Any]:
        self.ledger.verify_chain_integrity()
        shokudo = self.shokudos[shokudo_id]
        totals = self.ledger.totals(shokudo_id)
        return {
            "shokudo_id": shokudo_id,
            "shokudo_name": shokudo.name,
            "operator_nullifier": shokudo.operator_identity.nullifier_hash,
            "identity_backend": self.identity_backend,
            "chain_integrity": True,
            **totals,
            "records": [
                rec.to_public_dict()
                for rec in self.ledger._records
                if rec.shokudo_id == shokudo_id
            ],
        }

    def generate_sanpo_yoshi_report(self, shokudo_id: str) -> dict[str, Any]:
        """三方よしの可視化。数値は台帳からの機械集計であり、社会的効果の実証値ではない。"""
        audit = self.export_audit_report(shokudo_id)
        yen_per_meal = self.shokudos[shokudo_id].meals_estimate_yen_per_meal
        meals = audit["outflow_jpy"] // yen_per_meal if yen_per_meal else 0
        marche_rebate = sum(
            rec.amount_jpy
            for rec in self.ledger._records
            if rec.shokudo_id == shokudo_id and rec.event_type == LedgerEventType.MARCHE_REBATE
        )
        return {
            "generated_at": utc_now(),
            "disclaimer": "本レポートはプロトタイプ台帳の集計であり、政策効果の実証データではない。",
            "kodomo_yoshi": {
                "estimated_meals_from_expenditure": meals,
                "yen_per_meal_assumption": yen_per_meal,
                "note": "提供食数は支出額からの概算。実食数の現地記録が検証の本データになる。",
            },
            "unneisha_yoshi": {
                "inflow_jpy": audit["inflow_jpy"],
                "identity_method": self.shokudos[shokudo_id].operator_identity.method.value,
                "note": "運営者は属性情報ではなく nullifier のみで一意化される。",
            },
            "chiiki_yoshi": {
                "balance_jpy": audit["balance_jpy"],
                "marche_rebate_jpy": marche_rebate,
                "chain_integrity": audit["chain_integrity"],
                "note": "改ざん検知と残高は説明責任の補助指標。会計検査の代替ではない。",
            },
        }


def run_demo() -> dict[str, Any]:
    eco = KodomoShokudoMetaMarcheEcosystem(identity_backend="world_id_mock")
    shokudo = eco.register_shokudo(name="旭川子ども食堂デモ", operator_secret="operator-A")
    vendor = eco.register_vendor(name="地元野菜便", produce="旬の野菜セット", vendor_secret="vendor-B")

    eco.record_grant(shokudo_id=shokudo.shokudo_id, amount_jpy=120_000, note="自治体実証支援金（仮想）")
    eco.record_donation(
        shokudo_id=shokudo.shokudo_id,
        amount_jpy=8_000,
        donor_nullifier=sha256_hex("donor-C"),
        note="個人寄付（仮想）",
    )
    eco.record_sale_with_rebate(vendor_id=vendor.vendor_id, shokudo_id=shokudo.shokudo_id, amount_jpy=15_000)
    eco.record_expenditure(
        shokudo_id=shokudo.shokudo_id,
        operator_secret="operator-A",
        amount_jpy=24_000,
        note="食材調達",
        receipt_reference="R-2026-0819-001",
    )
    eco.dao_vote(proposal_id="rebate-rate", choice="keep-10pct", person_secret="voter-1")
    eco.dao_vote(proposal_id="rebate-rate", choice="raise-15pct", person_secret="voter-2")

    duplicate_blocked = False
    try:
        eco.register_shokudo(name="別名の食堂", operator_secret="operator-A")
    except DuplicateNullifierError:
        duplicate_blocked = True

    receipt_blocked = False
    try:
        eco.record_expenditure(
            shokudo_id=shokudo.shokudo_id,
            operator_secret="operator-A",
            amount_jpy=1_000,
            note="同一領収書の再請求",
            receipt_reference="R-2026-0819-001",
        )
    except DuplicateReceiptError:
        receipt_blocked = True

    proposal_summary = eco.gennai.summarize_proposal(
        "子ども食堂DAO実証",
        "World ID は必須前提ではなく、公的本人確認と並ぶ選択肢として設計する。",
    )
    copy = eco.gennai.vendor_copy(vendor.name, vendor.produce)

    report = {
        "proposal_summary": proposal_summary,
        "vendor_copy": copy,
        "duplicate_operator_blocked": duplicate_blocked,
        "duplicate_receipt_blocked": receipt_blocked,
        "dao_tally": eco.dao.tally("rebate-rate"),
        "audit": eco.export_audit_report(shokudo.shokudo_id),
        "sanpo_yoshi": eco.generate_sanpo_yoshi_report(shokudo.shokudo_id),
    }
    return report


def main() -> None:
    report = run_demo()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
