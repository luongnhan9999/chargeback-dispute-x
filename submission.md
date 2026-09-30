# Portal Submission Draft — ChargebackDisputeX

**Portal Track:** Builder  
**Contribution Type:** Intelligent Contracts  
**Network:** studionet (Chain ID: 61999)  
**Contract Address:** `0x4627469B6484De7ebdb3cA4CE7DB2DDef46b0765`  
**Evidence URL:** `https://github.com/luongnhan9999/chargeback-dispute-x`  

---

### Title
ChargebackDisputeX — Autonomous Adjudicated E-Commerce Chargeback Protocol

### Description (<1000 characters)
ChargebackDisputeX is an autonomous e-commerce escrow and chargeback primitive on GenLayer. It bridges the critical barrier to crypto payments: irreversible transactions and lack of buyer chargeback protection against logistics fraud.

When delivery disputes occur ("package lost, not received, or fake tracking"), GenLayer validators inspect authoritative carrier tracking portals (DHL, FedEx, UPS, USPS, 17track) via gl.nondet.web.render and adjudicate claims directly on-chain using an LLM consensus jury.

The custom validator strictly agrees on the MEANING of the logistics outcome via discrete enums (DELIVERED_CONFIRMED, LOST_OR_RETURNED, INVALID_OR_UNTRACKED, IN_TRANSIT), eliminating LLM phrasing discrepancies. Canonical host whitelisting and tracking binding prevent URL spoofing.

Reusable primitive for agentic AI shopping, Web3 merchant checkouts, and P2P commerce. Ships with 15 gltest tests and docs, live on studionet at 0x4627469B6484De7ebdb3cA4CE7DB2DDef46b0765.
