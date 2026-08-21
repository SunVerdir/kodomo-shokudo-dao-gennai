"""kodomo_shokudo_dao_meta_marche.py の単体テスト。

外部依存なし(標準ライブラリ unittest のみ)。
python -m unittest tests.test_core で実行する。
"""

from __future__ import annotations

import unittest

from kodomo_shokudo_dao_meta_marche import (
    AuditLedger,
    ChainIntegrityError,
    DuplicateNullifierError,
    DuplicateReceiptError,
    KodomoShokudoMetaMarcheEcosystem,
    LedgerEventType,
    PublicCredentialVerifier,
    VerificationMethod,
    WorldIDVerifier,
    run_demo,
    sha256_hex,
)


class WorldIDVerifierTests(unittest.TestCase):
    def test_same_secret_and_action_yields_same_nullifier(self) -> None:
        verifier = WorldIDVerifier(app_id="app_test")
        proof1 = verifier.verify(person_secret="alice", action="op_kyc", signal="sig")
        proof2 = verifier.verify(person_secret="alice", action="op_kyc", signal="sig")
        self.assertEqual(proof1.nullifier_hash, proof2.nullifier_hash)

    def test_different_action_yields_different_nullifier(self) -> None:
        verifier = WorldIDVerifier(app_id="app_test")
        proof1 = verifier.verify(person_secret="alice", action="op_kyc", signal="sig")
        proof2 = verifier.verify(person_secret="alice", action="vendor_kyc", signal="sig")
        self.assertNotEqual(proof1.nullifier_hash, proof2.nullifier_hash)

    def test_live_mode_raises_not_implemented(self) -> None:
        verifier = WorldIDVerifier(app_id="app_test", live=True)
        with self.assertRaises(NotImplementedError):
            verifier.verify(person_secret="alice", action="op_kyc", signal="sig")

    def test_rejects_non_world_id_level(self) -> None:
        verifier = WorldIDVerifier(app_id="app_test")
        with self.assertRaises(ValueError):
            verifier.verify(
                person_secret="alice",
                action="op_kyc",
                signal="sig",
                verification_level=VerificationMethod.PUBLIC_CREDENTIAL,
            )


class PublicCredentialVerifierTests(unittest.TestCase):
    def test_verify_returns_public_credential_method(self) -> None:
        verifier = PublicCredentialVerifier()
        proof = verifier.verify(subject_secret="alice", action="op_kyc", signal="sig")
        self.assertEqual(proof.method, VerificationMethod.PUBLIC_CREDENTIAL)
        self.assertTrue(proof.extra.get("placeholder"))


class AuditLedgerTests(unittest.TestCase):
    def test_append_builds_valid_chain(self) -> None:
        ledger = AuditLedger()
        ledger.append(
            event_type=LedgerEventType.GRANT,
            amount_jpy=1000,
            shokudo_id="ks_1",
            actor_nullifier="n1",
            note="test grant",
        )
        ledger.append(
            event_type=LedgerEventType.EXPENDITURE,
            amount_jpy=300,
            shokudo_id="ks_1",
            actor_nullifier="n1",
            note="test spend",
            receipt_reference="R-001",
        )
        self.assertTrue(ledger.verify_chain_integrity())
        totals = ledger.totals("ks_1")
        self.assertEqual(totals["inflow_jpy"], 1000)
        self.assertEqual(totals["outflow_jpy"], 300)
        self.assertEqual(totals["balance_jpy"], 700)

    def test_duplicate_receipt_reference_is_rejected(self) -> None:
        ledger = AuditLedger()
        ledger.append(
            event_type=LedgerEventType.EXPENDITURE,
            amount_jpy=100,
            shokudo_id="ks_1",
            actor_nullifier="n1",
            note="first",
            receipt_reference="R-DUP",
        )
        with self.assertRaises(DuplicateReceiptError):
            ledger.append(
                event_type=LedgerEventType.EXPENDITURE,
                amount_jpy=100,
                shokudo_id="ks_1",
                actor_nullifier="n1",
                note="second",
                receipt_reference="R-DUP",
            )

    def test_non_positive_amount_is_rejected(self) -> None:
        ledger = AuditLedger()
        with self.assertRaises(ValueError):
            ledger.append(
                event_type=LedgerEventType.GRANT,
                amount_jpy=0,
                shokudo_id="ks_1",
                actor_nullifier="n1",
                note="invalid",
            )

    def test_tampered_record_breaks_chain_integrity(self) -> None:
        ledger = AuditLedger()
        ledger.append(
            event_type=LedgerEventType.GRANT,
            amount_jpy=1000,
            shokudo_id="ks_1",
            actor_nullifier="n1",
            note="original",
        )
        ledger._records[0] = ledger._records[0].__class__(
            **{**vars(ledger._records[0]), "amount_jpy": 999999}
        )
        with self.assertRaises(ChainIntegrityError):
            ledger.verify_chain_integrity()


class EcosystemTests(unittest.TestCase):
    def _new_eco(self, identity_backend: str = "world_id_mock") -> KodomoShokudoMetaMarcheEcosystem:
        return KodomoShokudoMetaMarcheEcosystem(identity_backend=identity_backend)

    def test_register_shokudo_and_vendor(self) -> None:
        eco = self._new_eco()
        shokudo = eco.register_shokudo(name="テスト食堂", operator_secret="op-1")
        vendor = eco.register_vendor(name="テスト農園", produce="トマト", vendor_secret="vd-1")
        self.assertIn(shokudo.shokudo_id, eco.shokudos)
        self.assertIn(vendor.vendor_id, eco.vendors)

    def test_duplicate_operator_registration_is_blocked(self) -> None:
        eco = self._new_eco()
        eco.register_shokudo(name="食堂A", operator_secret="op-same")
        with self.assertRaises(DuplicateNullifierError):
            eco.register_shokudo(name="食堂B(別名義)", operator_secret="op-same")

    def test_duplicate_vendor_registration_is_blocked(self) -> None:
        eco = self._new_eco()
        eco.register_vendor(name="出店者A", produce="米", vendor_secret="vd-same")
        with self.assertRaises(DuplicateNullifierError):
            eco.register_vendor(name="出店者B(別名義)", produce="野菜", vendor_secret="vd-same")

    def test_expenditure_requires_matching_operator_secret(self) -> None:
        eco = self._new_eco()
        shokudo = eco.register_shokudo(name="食堂A", operator_secret="op-1")
        eco.record_grant(shokudo_id=shokudo.shokudo_id, amount_jpy=10_000, note="grant")
        with self.assertRaises(PermissionError):
            eco.record_expenditure(
                shokudo_id=shokudo.shokudo_id,
                operator_secret="op-DIFFERENT",
                amount_jpy=1_000,
                note="不正な支出報告",
                receipt_reference="R-100",
            )

    def test_expenditure_with_correct_secret_succeeds(self) -> None:
        eco = self._new_eco()
        shokudo = eco.register_shokudo(name="食堂A", operator_secret="op-1")
        eco.record_grant(shokudo_id=shokudo.shokudo_id, amount_jpy=10_000, note="grant")
        record = eco.record_expenditure(
            shokudo_id=shokudo.shokudo_id,
            operator_secret="op-1",
            amount_jpy=1_000,
            note="食材調達",
            receipt_reference="R-101",
        )
        self.assertEqual(record.amount_jpy, 1_000)

    def test_duplicate_receipt_blocked_via_ecosystem(self) -> None:
        eco = self._new_eco()
        shokudo = eco.register_shokudo(name="食堂A", operator_secret="op-1")
        eco.record_grant(shokudo_id=shokudo.shokudo_id, amount_jpy=10_000, note="grant")
        eco.record_expenditure(
            shokudo_id=shokudo.shokudo_id,
            operator_secret="op-1",
            amount_jpy=1_000,
            note="1回目",
            receipt_reference="R-DUP",
        )
        with self.assertRaises(DuplicateReceiptError):
            eco.record_expenditure(
                shokudo_id=shokudo.shokudo_id,
                operator_secret="op-1",
                amount_jpy=1_000,
                note="2回目(同じ領収書)",
                receipt_reference="R-DUP",
            )

    def test_sale_with_rebate_credits_shokudo(self) -> None:
        eco = self._new_eco()
        shokudo = eco.register_shokudo(name="食堂A", operator_secret="op-1")
        vendor = eco.register_vendor(name="出店者A", produce="米", vendor_secret="vd-1")
        sale, record = eco.record_sale_with_rebate(
            vendor_id=vendor.vendor_id,
            shokudo_id=shokudo.shokudo_id,
            amount_jpy=10_000,
            rebate_rate=0.1,
        )
        self.assertEqual(sale.rebate_to_shokudo_jpy, 1_000)
        self.assertEqual(record.amount_jpy, 1_000)
        self.assertEqual(record.event_type, LedgerEventType.MARCHE_REBATE)

    def test_dao_vote_one_person_one_vote(self) -> None:
        eco = self._new_eco()
        eco.dao_vote(proposal_id="p1", choice="A", person_secret="voter-1")
        eco.dao_vote(proposal_id="p1", choice="B", person_secret="voter-2")
        with self.assertRaises(DuplicateNullifierError):
            eco.dao_vote(proposal_id="p1", choice="B", person_secret="voter-1")
        tally = eco.dao.tally("p1")
        self.assertEqual(tally, {"A": 1, "B": 1})

    def test_public_credential_backend_is_used_when_selected(self) -> None:
        eco = self._new_eco(identity_backend="public_credential")
        shokudo = eco.register_shokudo(name="食堂A", operator_secret="op-1")
        self.assertEqual(
            shokudo.operator_identity.method,
            VerificationMethod.PUBLIC_CREDENTIAL,
        )

    def test_sanpo_yoshi_report_shape(self) -> None:
        eco = self._new_eco()
        shokudo = eco.register_shokudo(name="食堂A", operator_secret="op-1")
        eco.record_grant(shokudo_id=shokudo.shokudo_id, amount_jpy=40_000, note="grant")
        eco.record_expenditure(
            shokudo_id=shokudo.shokudo_id,
            operator_secret="op-1",
            amount_jpy=4_000,
            note="食材調達",
            receipt_reference="R-200",
        )
        report = eco.generate_sanpo_yoshi_report(shokudo.shokudo_id)
        self.assertIn("disclaimer", report)
        self.assertIn("kodomo_yoshi", report)
        self.assertIn("unneisha_yoshi", report)
        self.assertIn("chiiki_yoshi", report)
        self.assertEqual(report["kodomo_yoshi"]["estimated_meals_from_expenditure"], 10)

    def test_demo_runs(self) -> None:
        report = run_demo()
        self.assertTrue(report["duplicate_operator_blocked"])
        self.assertTrue(report["duplicate_receipt_blocked"])
        self.assertEqual(report["audit"]["balance_jpy"], 120_000 + 8_000 + 1_500 - 24_000)


class UtilTests(unittest.TestCase):
    def test_sha256_hex_is_deterministic(self) -> None:
        self.assertEqual(sha256_hex("abc"), sha256_hex("abc"))
        self.assertNotEqual(sha256_hex("abc"), sha256_hex("abd"))


if __name__ == "__main__":
    unittest.main()
