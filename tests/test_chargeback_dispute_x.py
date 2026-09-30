import pytest
import json
from gltest import *


@pytest.fixture
def contract(direct_deploy):
    return direct_deploy("contracts/chargeback_dispute_x.py")


def test_initial_state_and_domains(contract, direct_vm, direct_alice, direct_bob):
    assert contract.get_order_count() == 0
    assert contract.is_carrier_domain_allowed("dhl.com") is True
    assert contract.is_carrier_domain_allowed("fedex.com") is True
    assert contract.is_carrier_domain_allowed("ups.com") is True
    assert contract.is_carrier_domain_allowed("usps.com") is True
    assert contract.is_carrier_domain_allowed("17track.net") is True
    assert contract.is_carrier_domain_allowed("parcelsapp.com") is True
    assert contract.is_carrier_domain_allowed("fake-carrier.xyz") is False

    # Owner adds a new allowed carrier domain
    contract.add_allowed_carrier_domain("vnpost.vn")
    assert contract.is_carrier_domain_allowed("vnpost.vn") is True

    # Owner removes allowed carrier domain
    contract.remove_allowed_carrier_domain("vnpost.vn")
    assert contract.is_carrier_domain_allowed("vnpost.vn") is False

    # Non-owner cannot add allowed carrier domain
    direct_vm.sender = direct_bob
    with pytest.raises(Exception, match="Only contract owner can add carrier domains"):
        contract.add_allowed_carrier_domain("scam-carrier.com")

    # Non-owner cannot remove allowed carrier domain
    with pytest.raises(Exception, match="Only contract owner can remove carrier domains"):
        contract.remove_allowed_carrier_domain("dhl.com")


def test_create_order_success(contract, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    direct_vm.value = 5000

    oid = contract.create_order(
        seller=direct_bob,
        item_description="High-end Gaming Laptop RTX 4090",
        carrier_name="DHL",
        tracking_number="DHL123456789",
        tracking_url="https://www.dhl.com/en/express/tracking.html?AWB=DHL123456789"
    )

    assert oid == "1"
    assert contract.get_order_count() == 1

    order_json = json.loads(contract.get_order("1"))
    assert order_json["order_id"] == "1"
    assert order_json["buyer"] == direct_alice.as_hex.lower()
    assert order_json["seller"] == direct_bob.as_hex.lower()
    assert order_json["item_description"] == "High-end Gaming Laptop RTX 4090"
    assert order_json["carrier_name"] == "DHL"
    assert order_json["tracking_number"] == "DHL123456789"
    assert order_json["order_amount"] == "5000"
    assert order_json["seller_bond"] == "0"
    assert order_json["status"] == "CREATED"
    assert order_json["verdict"] == "PENDING"


def test_create_order_validation_failures(contract, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice

    # 1. Zero escrow deposit
    direct_vm.value = 0
    with pytest.raises(Exception, match="Order deposit must be greater than 0 GEN"):
        contract.create_order(
            seller=direct_bob,
            item_description="Laptop",
            carrier_name="DHL",
            tracking_number="DHL12345",
            tracking_url="https://dhl.com/track/dhl12345"
        )

    # 2. Too short item description
    direct_vm.value = 1000
    with pytest.raises(Exception, match="Item description must be substantive"):
        contract.create_order(
            seller=direct_bob,
            item_description="X",
            carrier_name="DHL",
            tracking_number="DHL12345",
            tracking_url="https://dhl.com/track/dhl12345"
        )

    # 3. Too short carrier name
    with pytest.raises(Exception, match="Carrier name is too short"):
        contract.create_order(
            seller=direct_bob,
            item_description="Valid Item Description",
            carrier_name="D",
            tracking_number="DHL12345",
            tracking_url="https://dhl.com/track/dhl12345"
        )

    # 4. Too short tracking number
    with pytest.raises(Exception, match="Tracking number is too short"):
        contract.create_order(
            seller=direct_bob,
            item_description="Valid Item Description",
            carrier_name="DHL",
            tracking_number="12",
            tracking_url="https://dhl.com/track/12"
        )

    # 5. Invalid URL scheme
    with pytest.raises(Exception, match="tracking_url must begin with http:// or https://"):
        contract.create_order(
            seller=direct_bob,
            item_description="Valid Item Description",
            carrier_name="DHL",
            tracking_number="DHL12345",
            tracking_url="ftp://dhl.com/track/DHL12345"
        )

    # 6. Non-whitelisted carrier domain (Canonical Host Validation)
    with pytest.raises(Exception, match="is not in the allowed carrier whitelist"):
        contract.create_order(
            seller=direct_bob,
            item_description="Valid Item Description",
            carrier_name="DHL",
            tracking_number="DHL12345",
            tracking_url="https://scam-carrier-lookup.com/track/DHL12345"
        )

    # 7. Tracking number not contained in URL (Canonical Tracking Binding Rule)
    with pytest.raises(Exception, match="must canonically contain the tracking number"):
        contract.create_order(
            seller=direct_bob,
            item_description="Valid Item Description",
            carrier_name="DHL",
            tracking_number="DHL99999",
            tracking_url="https://www.dhl.com/track/DIFFERENT_NUMBER"
        )


def test_deposit_seller_fulfillment_bond(contract, direct_vm, direct_alice, direct_bob, direct_charlie):
    direct_vm.sender = direct_alice
    direct_vm.value = 5000
    oid = contract.create_order(
        seller=direct_bob,
        item_description="Mechanical Keyboard",
        carrier_name="FEDEX",
        tracking_number="FDX987654",
        tracking_url="https://fedex.com/tracking?tracknumbers=FDX987654"
    )

    # Stranger (charlie) cannot deposit seller bond
    direct_vm.sender = direct_charlie
    direct_vm.value = 1000
    with pytest.raises(Exception, match="Only designated seller can deposit fulfillment bond"):
        contract.deposit_seller_fulfillment_bond(oid)

    # Seller deposits 0 GEN -> reverts
    direct_vm.sender = direct_bob
    direct_vm.value = 0
    with pytest.raises(Exception, match="Bond must be greater than 0 GEN"):
        contract.deposit_seller_fulfillment_bond(oid)

    # Seller deposits 1000 GEN bond successfully
    direct_vm.value = 1000
    contract.deposit_seller_fulfillment_bond(oid)

    order_json = json.loads(contract.get_order(oid))
    assert order_json["seller_bond"] == "1000"


def test_confirm_delivery_and_release_happy_path(contract, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    direct_vm.value = 6000
    oid = contract.create_order(
        seller=direct_bob,
        item_description="Smartphone OLED 256GB",
        carrier_name="UPS",
        tracking_number="1Z9999999999999999",
        tracking_url="https://www.ups.com/track?loc=en_US&tracknum=1Z9999999999999999"
    )

    # Seller deposits 1500 bond
    direct_vm.sender = direct_bob
    direct_vm.value = 1500
    contract.deposit_seller_fulfillment_bond(oid)

    # Seller cannot confirm delivery
    direct_vm.sender = direct_bob
    with pytest.raises(Exception, match="Only buyer can directly release escrow"):
        contract.confirm_delivery_and_release(oid)

    # Buyer confirms receipt directly
    direct_vm.sender = direct_alice
    contract.confirm_delivery_and_release(oid)

    order_json = json.loads(contract.get_order(oid))
    assert order_json["status"] == "COMPLETED"
    assert order_json["verdict"] == "DELIVERED_CONFIRMED"
    assert "Buyer directly confirmed" in order_json["reason"]

    # Re-confirming completed order reverts
    with pytest.raises(Exception, match="Order is not in active CREATED state"):
        contract.confirm_delivery_and_release(oid)


def test_dispute_chargeback_delivered_confirmed(contract, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    direct_vm.value = 8000
    oid = contract.create_order(
        seller=direct_bob,
        item_description="Graphics Card RTX 4080",
        carrier_name="DHL",
        tracking_number="DHL88887777",
        tracking_url="https://www.dhl.com/track/DHL88887777"
    )

    direct_vm.sender = direct_bob
    direct_vm.value = 2000
    contract.deposit_seller_fulfillment_bond(oid)

    # Mock web response: Package delivered to front porch
    direct_vm.mock_web("DHL88887777", {
        "status": 200,
        "body": "DHL Express Tracking: DHL88887777 - Status: DELIVERED. Signed by recipient J. Doe at front door on 2026-09-28 14:30."
    })

    # Mock LLM verdict: DELIVERED_CONFIRMED
    direct_vm.mock_llm(".*", json.dumps({
        "verdict": "DELIVERED_CONFIRMED",
        "confidence": 98,
        "reason": "Tracking explicitly confirms package was signed and delivered to recipient."
    }))

    # Buyer triggers dispute
    direct_vm.sender = direct_alice
    contract.dispute_delivery_chargeback(oid)

    order_json = json.loads(contract.get_order(oid))
    assert order_json["status"] == "COMPLETED"
    assert order_json["verdict"] == "DELIVERED_CONFIRMED"
    assert "delivered" in order_json["reason"].lower()


def test_dispute_chargeback_lost_or_returned(contract, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    direct_vm.value = 4000
    oid = contract.create_order(
        seller=direct_bob,
        item_description="Wireless Noise-Canceling Headphones",
        carrier_name="FEDEX",
        tracking_number="FDX44332211",
        tracking_url="https://fedex.com/track?tracknumbers=FDX44332211"
    )

    direct_vm.sender = direct_bob
    direct_vm.value = 1000
    contract.deposit_seller_fulfillment_bond(oid)

    # Mock web response: Damaged in transit, returned to sender
    direct_vm.mock_web("FDX44332211", {
        "status": 200,
        "body": "FedEx Ground Tracking: FDX44332211. Package damaged severely in transit at hub sorting center. Return to sender processed."
    })

    # Mock LLM verdict: LOST_OR_RETURNED
    direct_vm.mock_llm(".*", json.dumps({
        "verdict": "LOST_OR_RETURNED",
        "confidence": 96,
        "reason": "Parcel suffered transit damage and was aborted and returned to sender."
    }))

    # Seller can also trigger dispute
    direct_vm.sender = direct_bob
    contract.dispute_delivery_chargeback(oid)

    order_json = json.loads(contract.get_order(oid))
    assert order_json["status"] == "REFUNDED"
    assert order_json["verdict"] == "LOST_OR_RETURNED"
    assert "returned" in order_json["reason"].lower() or "damage" in order_json["reason"].lower()


def test_dispute_chargeback_invalid_or_untracked(contract, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    direct_vm.value = 3500
    oid = contract.create_order(
        seller=direct_bob,
        item_description="Collectible Mechanical Watch",
        carrier_name="USPS",
        tracking_number="USPS94001000",
        tracking_url="https://tools.usps.com/go/TrackConfirmAction?tLabels=USPS94001000"
    )

    direct_vm.sender = direct_bob
    direct_vm.value = 1000
    contract.deposit_seller_fulfillment_bond(oid)

    # Mock web: Tracking number not found in carrier database
    direct_vm.mock_web("USPS94001000", {
        "status": 200,
        "body": "USPS Tracking: Tracking number USPS94001000 is not recognized. No shipment records exist for this identifier."
    })

    # Mock LLM verdict: INVALID_OR_UNTRACKED
    direct_vm.mock_llm(".*", json.dumps({
        "verdict": "INVALID_OR_UNTRACKED",
        "confidence": 99,
        "reason": "Carrier records confirm tracking number does not exist or has expired."
    }))

    direct_vm.sender = direct_alice
    contract.dispute_delivery_chargeback(oid)

    order_json = json.loads(contract.get_order(oid))
    assert order_json["status"] == "REFUNDED"
    assert order_json["verdict"] == "INVALID_OR_UNTRACKED"


def test_dispute_chargeback_in_transit(contract, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    direct_vm.value = 7000
    oid = contract.create_order(
        seller=direct_bob,
        item_description="Mirrorless Camera 4K",
        carrier_name="UPS",
        tracking_number="1Z888777666",
        tracking_url="https://www.ups.com/track?tracknum=1Z888777666"
    )

    direct_vm.sender = direct_bob
    direct_vm.value = 2000
    contract.deposit_seller_fulfillment_bond(oid)

    # Mock web: In transit, out for delivery today
    direct_vm.mock_web("1Z888777666", {
        "status": 200,
        "body": "UPS Tracking: 1Z888777666. Status: On the Way. In transit between regional distribution center and local facility."
    })

    # Mock LLM verdict: IN_TRANSIT
    direct_vm.mock_llm(".*", json.dumps({
        "verdict": "IN_TRANSIT",
        "confidence": 92,
        "reason": "Package is actively moving in transit through regional facilities, delivery pending."
    }))

    direct_vm.sender = direct_alice
    contract.dispute_delivery_chargeback(oid)

    order_json = json.loads(contract.get_order(oid))
    # Order status MUST remain CREATED so escrow stays active and can be finalized later!
    assert order_json["status"] == "CREATED"
    assert order_json["verdict"] == "IN_TRANSIT"
    assert "transit" in order_json["reason"].lower()


def test_dispute_url_offline_or_404_fallback(contract, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    direct_vm.value = 2500
    oid = contract.create_order(
        seller=direct_bob,
        item_description="Vintage Vinyl Records",
        carrier_name="DHL",
        tracking_number="DHL55443322",
        tracking_url="https://dhl.com/track/DHL55443322"
    )

    # Mock web: 404 Not Found
    direct_vm.mock_web("DHL55443322", {
        "status": 404,
        "body": "404 Not Found - Server Error"
    })

    direct_vm.sender = direct_alice
    contract.dispute_delivery_chargeback(oid)

    order_json = json.loads(contract.get_order(oid))
    assert order_json["status"] == "REFUNDED"
    assert order_json["verdict"] == "INVALID_OR_UNTRACKED"
    assert "inaccessible" in order_json["reason"].lower() or "offline" in order_json["reason"].lower()


def test_dispute_invalid_llm_json_fallback(contract, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    direct_vm.value = 3000
    oid = contract.create_order(
        seller=direct_bob,
        item_description="Tablet Computer",
        carrier_name="FEDEX",
        tracking_number="FDX11223344",
        tracking_url="https://fedex.com/track/FDX11223344"
    )

    direct_vm.mock_web("FDX11223344", {
        "status": 200,
        "body": "FedEx Tracking Details for FDX11223344."
    })
    # Non-JSON garbage response from LLM
    direct_vm.mock_llm(".*", "This response is not in JSON format at all.")

    direct_vm.sender = direct_alice
    contract.dispute_delivery_chargeback(oid)

    order_json = json.loads(contract.get_order(oid))
    assert order_json["status"] == "REFUNDED"
    assert order_json["verdict"] == "INVALID_OR_UNTRACKED"


def test_dispute_low_confidence_fallback(contract, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    direct_vm.value = 5000
    oid = contract.create_order(
        seller=direct_bob,
        item_description="Designer Handbag",
        carrier_name="UPS",
        tracking_number="1Z444555666",
        tracking_url="https://ups.com/track/1Z444555666"
    )

    direct_vm.mock_web("1Z444555666", {
        "status": 200,
        "body": "Partial ambiguous tracking data string."
    })
    # Confidence is 40 (< 65)
    direct_vm.mock_llm(".*", json.dumps({
        "verdict": "DELIVERED_CONFIRMED",
        "confidence": 40,
        "reason": "Unclear scan snippet."
    }))

    direct_vm.sender = direct_alice
    contract.dispute_delivery_chargeback(oid)

    order_json = json.loads(contract.get_order(oid))
    # Low confidence delivery falls back to INVALID_OR_UNTRACKED
    assert order_json["status"] == "REFUNDED"
    assert order_json["verdict"] == "INVALID_OR_UNTRACKED"


def test_dispute_non_participant_reverts(contract, direct_vm, direct_alice, direct_bob, direct_charlie):
    direct_vm.sender = direct_alice
    direct_vm.value = 2000
    oid = contract.create_order(
        seller=direct_bob,
        item_description="Smart Watch",
        carrier_name="DHL",
        tracking_number="DHL33221100",
        tracking_url="https://dhl.com/track/DHL33221100"
    )

    # Charlie (third-party) attempts to dispute
    direct_vm.sender = direct_charlie
    with pytest.raises(Exception, match="Only buyer or seller can trigger dispute adjudication"):
        contract.dispute_delivery_chargeback(oid)


def test_dispute_non_created_state_reverts(contract, direct_vm, direct_alice, direct_bob):
    direct_vm.sender = direct_alice
    direct_vm.value = 3000
    oid = contract.create_order(
        seller=direct_bob,
        item_description="Audio Amplifier",
        carrier_name="USPS",
        tracking_number="USPS11223399",
        tracking_url="https://usps.com/track/USPS11223399"
    )

    # Direct confirmation moves status to COMPLETED
    contract.confirm_delivery_and_release(oid)

    with pytest.raises(Exception, match="Order is not eligible for dispute adjudication"):
        contract.dispute_delivery_chargeback(oid)


def test_multi_order_isolation(contract, direct_vm, direct_alice, direct_bob):
    # Order 1: Delivered
    direct_vm.sender = direct_alice
    direct_vm.value = 6000
    oid1 = contract.create_order(
        seller=direct_bob,
        item_description="Laptop Dell XPS",
        carrier_name="DHL",
        tracking_number="DHL_ORDER_1",
        tracking_url="https://dhl.com/track/DHL_ORDER_1"
    )

    # Order 2: Lost
    oid2 = contract.create_order(
        seller=direct_bob,
        item_description="Sony Headphones",
        carrier_name="FEDEX",
        tracking_number="FDX_ORDER_2",
        tracking_url="https://fedex.com/track/FDX_ORDER_2"
    )

    assert oid1 == "1"
    assert oid2 == "2"
    assert contract.get_order_count() == 2

    # Mock order 1 as DELIVERED
    direct_vm.mock_web("DHL_ORDER_1", {"status": 200, "body": "DHL Package DHL_ORDER_1 delivered successfully."})
    direct_vm.mock_llm(".*DHL_ORDER_1.*", json.dumps({"verdict": "DELIVERED_CONFIRMED", "confidence": 99, "reason": "Delivered successfully."}))
    contract.dispute_delivery_chargeback(oid1)

    # Mock order 2 as LOST
    direct_vm.mock_web("FDX_ORDER_2", {"status": 200, "body": "FedEx Package FDX_ORDER_2 lost in transit."})
    direct_vm.mock_llm(".*FDX_ORDER_2.*", json.dumps({"verdict": "LOST_OR_RETURNED", "confidence": 98, "reason": "Lost in transit."}))
    contract.dispute_delivery_chargeback(oid2)

    order1 = json.loads(contract.get_order(oid1))
    order2 = json.loads(contract.get_order(oid2))

    assert order1["verdict"] == "DELIVERED_CONFIRMED"
    assert order1["status"] == "COMPLETED"

    assert order2["verdict"] == "LOST_OR_RETURNED"
    assert order2["status"] == "REFUNDED"
