# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from dataclasses import dataclass
import json

try:
    gl.UserError = gl.vm.UserError
except Exception:
    pass


def _addr_str(addr: Address) -> str:
    """Safely format an Address instance into a lowercase hex string."""
    try:
        return addr.as_hex.lower()
    except Exception:
        return str(addr).lower()


def _get_sender() -> Address:
    """Safely obtain transaction sender across GenVM runtime versions."""
    try:
        return gl.message.sender
    except Exception:
        try:
            return gl.message.sender_address
        except Exception:
            raise gl.UserError("Cannot resolve sender address.")


def _safe_transfer(recipient: Address, amount: bigint) -> None:
    """Safely disburse native GEN to an address using official GenLayer SDK pattern."""
    if amount <= bigint(0):
        return
    gl.get_contract_at(recipient).emit_transfer(value=u256(int(amount)))


DEFAULT_CARRIER_DOMAINS = (
    "dhl.com",
    "www.dhl.com",
    "fedex.com",
    "www.fedex.com",
    "ups.com",
    "www.ups.com",
    "usps.com",
    "tools.usps.com",
    "parcelsapp.com",
    "www.parcelsapp.com",
    "17track.net",
    "www.17track.net",
    "trackingmore.com",
    "www.trackingmore.com",
    "royalmail.com",
    "www.royalmail.com",
    "mock-carrier.genlayer.com",
)


def _parse_url_host(raw_url: str) -> str:
    """Extract and validate normalized hostname from URL."""
    clean = raw_url.strip()
    if "?" in clean:
        clean = clean.split("?")[0]
    if "#" in clean:
        clean = clean.split("#")[0]
    clean = clean.strip()

    if clean.startswith("https://"):
        rest = clean[8:]
    elif clean.startswith("http://"):
        rest = clean[7:]
    else:
        raise gl.UserError("URL must begin with http:// or https://")

    host = rest.split("/", 1)[0].strip().lower()
    if ":" in host:
        host = host.split(":")[0].strip()
    if not host:
        raise gl.UserError("Invalid URL: missing host")
    return host


@allow_storage
@dataclass
class OrderEscrow:
    order_id: str
    buyer: Address
    seller: Address
    order_item_description: str
    carrier_name: str          # e.g., "DHL", "FEDEX", "UPS", "USPS"
    tracking_number: str       # Carrier tracking code
    tracking_url: str          # Authoritative carrier tracking page
    order_amount: bigint       # Purchase amount locked in escrow
    seller_bond: bigint        # Seller commitment bond (slashed if fraud/untracked)
    status: str                # "CREATED", "DISPUTED", "COMPLETED", "REFUNDED"
    verdict: str               # "PENDING", "DELIVERED_CONFIRMED", "LOST_OR_RETURNED", "INVALID_OR_UNTRACKED", "IN_TRANSIT"
    reason: str                # AI consensus evaluation breakdown
    created_at: bigint
    resolved_at: bigint


class Contract(gl.Contract):
    """
    ChargebackDisputeX: Autonomous Adjudicated E-Commerce Chargeback Protocol
    Track: Agentic Commerce Infrastructure / Onchain Justice
    """
    owner: Address
    order_count: bigint
    orders: TreeMap[str, OrderEscrow]
    custom_allowed_domains: TreeMap[str, bool]

    def __init__(self):
        # GenVM automatically initializes TreeMap storage fields to empty.
        # DO NOT assign TreeMap() in __init__ (Rule #2).
        self.owner = _get_sender()
        self.order_count = bigint(0)

    def _parse_llm_json(self, text: str) -> dict:
        """Safely parse LLM responses, stripping markdown wrappers if present."""
        try:
            cleaned = str(text).strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            return {
                "verdict": "INVALID_OR_UNTRACKED",
                "confidence": 0,
                "reason": f"Failed to parse LLM JSON: {str(e)[:100]}"
            }

    @gl.public.write
    def add_allowed_carrier_domain(self, domain: str) -> None:
        """Owner can whitelist additional legitimate carrier domains."""
        if _addr_str(_get_sender()) != _addr_str(self.owner):
            raise gl.UserError("Only contract owner can add carrier domains.")
        clean = domain.strip().lower()
        if len(clean) < 3:
            raise gl.UserError("Invalid domain name.")
        self.custom_allowed_domains[clean] = True

    @gl.public.write
    def remove_allowed_carrier_domain(self, domain: str) -> None:
        """Owner can remove custom allowed carrier domain."""
        if _addr_str(_get_sender()) != _addr_str(self.owner):
            raise gl.UserError("Only contract owner can remove carrier domains.")
        clean = domain.strip().lower()
        self.custom_allowed_domains[clean] = False

    @gl.public.view
    def is_carrier_domain_allowed(self, domain: str) -> bool:
        """Check if carrier domain is whitelisted."""
        clean = domain.strip().lower()
        if clean in DEFAULT_CARRIER_DOMAINS:
            return True
        return clean in self.custom_allowed_domains and self.custom_allowed_domains[clean]

    @gl.public.write.payable
    def create_order(
        self,
        seller: Address,
        item_description: str,
        carrier_name: str,
        tracking_number: str,
        tracking_url: str
    ) -> str:
        """
        Buyer creates an escrow order, depositing payment value.
        """
        deposit = bigint(gl.message.value)
        if deposit <= bigint(0):
            raise gl.UserError("Order deposit must be greater than 0 GEN.")

        clean_item = item_description.strip()
        clean_carrier = carrier_name.strip().upper()
        clean_tracking = tracking_number.strip().upper()
        clean_url = tracking_url.strip()

        if len(clean_item) < 3:
            raise gl.UserError("Item description must be substantive.")
        if len(clean_carrier) < 2:
            raise gl.UserError("Carrier name is too short.")
        if len(clean_tracking) < 4:
            raise gl.UserError("Tracking number is too short.")

        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            raise gl.UserError("tracking_url must begin with http:// or https://")

        # Canonical Host Validation
        host = _parse_url_host(clean_url)
        is_allowed = (host in DEFAULT_CARRIER_DOMAINS) or (
            host in self.custom_allowed_domains and self.custom_allowed_domains[host]
        )
        if not is_allowed:
            raise gl.UserError(f"Tracking domain '{host}' is not in the allowed carrier whitelist.")

        # Canonical Tracking Number Binding (Preclude URL spoofing / Replay attacks)
        if clean_tracking.lower() not in clean_url.lower():
            raise gl.UserError(f"Tracking URL must canonically contain the tracking number '{clean_tracking}'.")

        self.order_count += bigint(1)
        oid = str(self.order_count)

        self.orders[oid] = OrderEscrow(
            order_id=oid,
            buyer=_get_sender(),
            seller=seller,
            order_item_description=clean_item,
            carrier_name=clean_carrier,
            tracking_number=clean_tracking,
            tracking_url=clean_url,
            order_amount=deposit,
            seller_bond=bigint(0),
            status="CREATED",
            verdict="PENDING",
            reason="Order funded in escrow. Waiting for delivery or seller bond.",
            created_at=self.order_count,
            resolved_at=bigint(0)
        )

        return oid

    @gl.public.write.payable
    def deposit_seller_fulfillment_bond(self, order_id: str) -> None:
        """
        Seller stakes a fulfillment bond (commitment to deliver item accurately).
        """
        if order_id not in self.orders:
            raise gl.UserError("Order not found.")

        order = self.orders[order_id]
        if _addr_str(_get_sender()) != _addr_str(order.seller):
            raise gl.UserError("Only designated seller can deposit fulfillment bond.")

        bond = bigint(gl.message.value)
        if bond <= bigint(0):
            raise gl.UserError("Bond must be greater than 0 GEN.")

        if order.status != "CREATED":
            raise gl.UserError("Cannot deposit bond to completed or refunded order.")

        order.seller_bond += bond
        self.orders[order_id] = order

    @gl.public.write
    def confirm_delivery_and_release(self, order_id: str) -> None:
        """
        Happy path: Buyer directly confirms parcel receipt and releases funds to seller.
        """
        if order_id not in self.orders:
            raise gl.UserError("Order not found.")

        order = self.orders[order_id]
        if _addr_str(_get_sender()) != _addr_str(order.buyer):
            raise gl.UserError("Only buyer can directly release escrow.")

        if order.status != "CREATED":
            raise gl.UserError("Order is not in active CREATED state.")

        order.status = "COMPLETED"
        order.verdict = "DELIVERED_CONFIRMED"
        order.reason = "Buyer directly confirmed delivery receipt."
        order.resolved_at = self.order_count
        self.orders[order_id] = order

        total_seller_payout = order.order_amount + order.seller_bond
        _safe_transfer(order.seller, total_seller_payout)

    @gl.public.write
    def dispute_delivery_chargeback(self, order_id: str) -> None:
        """
        Buyer or Seller opens a chargeback dispute.
        Validators fetch the authoritative carrier tracking URL and adjudicate status.
        """
        if order_id not in self.orders:
            raise gl.UserError("Order not found.")

        order = self.orders[order_id]
        if order.status != "CREATED":
            raise gl.UserError("Order is not eligible for dispute adjudication.")

        caller_hex = _addr_str(_get_sender())
        if caller_hex != _addr_str(order.buyer) and caller_hex != _addr_str(order.seller):
            raise gl.UserError("Only buyer or seller can trigger dispute adjudication.")

        carrier_local = str(order.carrier_name)
        tracking_num_local = str(order.tracking_number)
        tracking_url_local = str(order.tracking_url)

        def leader_fn():
            web_content = ""
            try:
                res = gl.nondet.web.render(tracking_url_local, mode="text")
                if hasattr(res, "content"):
                    web_content = res.content
                elif isinstance(res, dict) and "body" in res:
                    web_content = res["body"]
                else:
                    web_content = str(res)
            except Exception:
                web_content = ""

            lower_web = web_content[:500].lower() if web_content else ""
            if len(web_content.strip()) < 15 or "404 not found" in lower_web or "access denied" in lower_web:
                return {
                    "verdict": "INVALID_OR_UNTRACKED",
                    "confidence": 100,
                    "reason": "Carrier tracking URL is offline, blank, or inaccessible."
                }

            snippet = web_content[:4000]

            prompt = f"""You are the Decentralized Carrier & E-Commerce Logistics Arbiter on GenLayer.
Evaluate the carrier tracking data for TRACKING NUMBER: {tracking_num_local} with CARRIER: {carrier_local}.
Determine the delivery status of the shipment.

CARRIER TRACKING DATA (from {tracking_url_local}):
\"\"\"
{snippet}
\"\"\"

DISCRETE CLASSIFICATION RULES:
Classify into strictly ONE of the following outcomes:
- "DELIVERED_CONFIRMED": Carrier tracking explicitly shows the parcel was delivered to recipient/address.
- "LOST_OR_RETURNED": Carrier marks package as lost in transit, damaged, aborted, or returned to sender.
- "INVALID_OR_UNTRACKED": Tracking number is not found, invalid, expired, or non-existent in carrier records.
- "IN_TRANSIT": Package is actively moving in transit or out for delivery, not yet delivered but not lost.

OUTPUT FORMAT:
Respond ONLY with a VALID JSON object (no markdown, no backticks):
{{
  "verdict": "DELIVERED_CONFIRMED" | "LOST_OR_RETURNED" | "INVALID_OR_UNTRACKED" | "IN_TRANSIT",
  "confidence": <integer from 0 to 100>,
  "reason": "<clear explanation max 220 characters>"
}}"""

            try:
                raw_res = gl.nondet.exec_prompt(prompt, response_format="json")
                parsed = None
                if isinstance(raw_res, dict):
                    parsed = raw_res
                elif hasattr(raw_res, "content") and isinstance(raw_res.content, dict):
                    parsed = raw_res.content
                else:
                    text = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
                    cleaned = str(text).strip()
                    if cleaned.startswith("```json"):
                        cleaned = cleaned[7:]
                    elif cleaned.startswith("```"):
                        cleaned = cleaned[3:]
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    parsed = json.loads(cleaned.strip())

                verdict_candidate = str(parsed.get("verdict", "INVALID_OR_UNTRACKED")).strip().upper()
                valid_verdicts = ("DELIVERED_CONFIRMED", "LOST_OR_RETURNED", "INVALID_OR_UNTRACKED", "IN_TRANSIT")
                if verdict_candidate not in valid_verdicts:
                    verdict_candidate = "INVALID_OR_UNTRACKED"

                try:
                    conf = int(parsed.get("confidence", 0))
                    conf = max(0, min(100, conf))
                except Exception:
                    conf = 50

                if conf < 65 and verdict_candidate != "IN_TRANSIT":
                    verdict_candidate = "INVALID_OR_UNTRACKED"

                reason_str = str(parsed.get("reason", "Tracking verified by AI jury."))[:220]

                return {
                    "verdict": verdict_candidate,
                    "confidence": conf,
                    "reason": reason_str
                }
            except Exception as e:
                return {
                    "verdict": "INVALID_OR_UNTRACKED",
                    "confidence": 0,
                    "reason": f"Evaluation error: {str(e)[:100]}"
                }

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False
            leader = leader_res.calldata
            if not isinstance(leader, dict) or "verdict" not in leader:
                return False

            valid_verdicts = ("DELIVERED_CONFIRMED", "LOST_OR_RETURNED", "INVALID_OR_UNTRACKED", "IN_TRANSIT")
            l_verdict = str(leader.get("verdict", "")).strip().upper()
            if l_verdict not in valid_verdicts:
                return False

            mine = leader_fn()
            m_verdict = str(mine.get("verdict", "")).strip().upper()

            # DISCRETE EQUIVALENCE: 100% agreement on discrete logistics outcome
            return l_verdict == m_verdict

        adjudication_res = gl.vm.run_nondet(leader_fn, validator_fn)
        if isinstance(adjudication_res, dict):
            final_res = adjudication_res
        else:
            final_res = self._parse_llm_json(str(adjudication_res))

        verdict = str(final_res.get("verdict", "INVALID_OR_UNTRACKED")).strip().upper()
        valid_verdicts = ("DELIVERED_CONFIRMED", "LOST_OR_RETURNED", "INVALID_OR_UNTRACKED", "IN_TRANSIT")
        if verdict not in valid_verdicts:
            verdict = "INVALID_OR_UNTRACKED"

        reason = str(final_res.get("reason", "Consensus concluded."))

        order.verdict = verdict
        order.reason = reason
        order.resolved_at = self.order_count

        if verdict == "DELIVERED_CONFIRMED":
            # Shipment successful: Disburse payment + seller bond to seller
            order.status = "COMPLETED"
            self.orders[order_id] = order

            total_seller = order.order_amount + order.seller_bond
            _safe_transfer(order.seller, total_seller)

        elif verdict in ("LOST_OR_RETURNED", "INVALID_OR_UNTRACKED"):
            # Shipment failed or fraudulent: 100% refund to buyer + seller bond awarded to buyer as indemnity
            order.status = "REFUNDED"
            self.orders[order_id] = order

            total_buyer_refund = order.order_amount + order.seller_bond
            _safe_transfer(order.buyer, total_buyer_refund)

        else:
            # IN_TRANSIT: Package is still moving legitimately; maintain escrow in CREATED state
            order.status = "CREATED"
            self.orders[order_id] = order

    @gl.public.view
    def get_order(self, order_id: str) -> str:
        """Retrieve details of an order escrow as a JSON string."""
        if order_id not in self.orders:
            raise gl.UserError("Order not found.")
        o = self.orders[order_id]
        return json.dumps({
            "order_id": o.order_id,
            "buyer": _addr_str(o.buyer),
            "seller": _addr_str(o.seller),
            "item_description": o.order_item_description,
            "carrier_name": o.carrier_name,
            "tracking_number": o.tracking_number,
            "tracking_url": o.tracking_url,
            "order_amount": str(o.order_amount),
            "seller_bond": str(o.seller_bond),
            "status": o.status,
            "verdict": o.verdict,
            "reason": o.reason,
            "created_at": str(o.created_at),
            "resolved_at": str(o.resolved_at)
        })

    @gl.public.view
    def get_order_count(self) -> int:
        return int(self.order_count)

    @gl.public.view
    def get_owner(self) -> str:
        return _addr_str(self.owner)
