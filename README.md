# Corrugated ERP – Corrugated Box & Packaging ERP for ERPNext

Corrugated ERP turns ERPNext (v15 / v16) into a complete ERP for corrugated box plants: box specification and
costing, kraft reel tracking, deckle planning, stage-wise production, die & plate tracking, quality
certificates and dispatch by bundles. It is built for the semi-automatic plants (single facer + pasting +
printing + slotting/die-cutting + stitching) that make up most of the Indian industry, and works the same
for automatic plants.

Everything else (accounts, GST / e-invoice via India Compliance, purchase, sales, HR, payroll) stays standard
ERPNext, so the app upgrades cleanly with ERPNext.

---

## 1. Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/<your-org>/corrugated_erp.git     # or copy this folder into apps/
bench --site <site> install-app corrugated_erp
bench --site <site> migrate
bench build --app corrugated_erp
```

The installer:

* adds custom fields on Item, Quotation/Sales Order/Delivery Note/Sales Invoice items, Work Order,
  Purchase Receipt and Stock Entry
* creates item groups **Kraft Paper**, **Corrugated Boxes**, **Corrugation Consumables**
* loads flute types (A, B, C, E, F), box styles (RSC, HSC, FOL, Tray, Sheet, Partition), 8 production
  stages, 13 quality parameters and standard reel deckles (28"–72")
* sets **Manufacturing Settings → Backflush Raw Materials Based On = Material Transferred for Manufacture**
  (so finished goods are costed on the paper actually used) and, on v16, **Transfer Extra Materials % = 20**.
  On v15 there is no separate setting; if a transfer is refused, raise *Overproduction Percentage for Work Order*.
* creates four workspaces: **Corrugated ERP** (management), **Box Shop Floor**, **Reel Store** and **Box Sales**, each shown to the
  matching ERPNext roles, plus the **Shop Floor Entry** page for operators on a phone or tablet

Keep **Manufacturing Settings → Validate Components Quantities Per BOM** switched off: reel weights and actual
gum / ink are transferred as used, not as per BOM.

Upgrading from 0.1: `bench --site <site> migrate` runs the upgrade patch that fills the new fields.

## 2. Go-live checklist (functional consultant)

| # | Setup | Where |
|---|---|---|
| 1 | Company, warehouses: **Reel Store**, **WIP**, **Finished Boxes**, **Scrap** | Warehouse |
| 2 | Machines: Single Facer, Pasting, Printer, Rotary Slotter, Die Punch, Stitching | Workstation |
| 3 | Kraft paper items – one per BF + GSM + shade, UOM **Kg**, tick **Is Kraft Paper** (batch tracking is switched on automatically) | Item |
| 4 | Consumables: gum/starch, stitching wire, ink, **paper scrap** item | Item |
| 5 | Paper rates per kg in the buying price list | Item Price |
| 6 | Defaults: price lists, warehouses, glue flap, waste %, conversion cost, deckles | Corrugation Settings |
| 7 | Check flute take-up factors against your corrugator rolls | Flute Type |
| 8 | Opening reels: **Reel Inward** with *Opening Stock* ticked | Reel Inward |
| 9 | Customers' boxes: **Box Specification** → *Create Item & BOM* → **Box Costing** | Box Specification |
| 10 | Dies / plates already in the plant | Box Tooling |
| 11 | Minimum margin %, margin approver role, artwork block, weight tolerance | Corrugation Settings → Controls |
| 12 | Second plant / company: its own warehouses, price lists, reel series and rates | Corrugation Plant |
| 13 | Piece rates for contract labour (pasting, stitching ...) | Production Stage |
| 14 | Accounts Settings → *Over Billing Allowance* 1–2 % so the Purchase Invoice can follow the mill's invoice weight | Accounts Settings |

**Import templates** (Data Import tool) are in `corrugated_erp/public/templates/` and on the site at
`/assets/corrugated_erp/templates/`: `kraft_paper_items.csv`, `box_specifications.csv` (with layers), `box_tooling.csv`,
`opening_reels.csv` (Reel Inward with *Opening Stock*; tick *Submit after import*).

## 3. Business flow

```
Enquiry ─► Box Specification ─► Box Costing ─► Quotation / Sales Order
                │ (Create Item & BOM)                     │
                ▼                                         ▼
          Box Item + BOM (per 1000 boxes)           Work Order
                                                          │
Paper Requirement Planning ─► Material Request ─► Purchase Order
                                                        │
Reel Inward (weight shortage → debit note) ─► Purchase Receipt   Deckle Plan (reel width, outs)
                    │ (reels + batches + labels)          │
                    ▼                                     ▼
       Paper Reel stock ── Reel Slitting (wide → narrow) ─► Production Entry: Corrugation
                                                   (reels + balance weights → paper transfer to WIP)
                                                          │
                                       Pasting ► Printing ► Slotting / Die-cut ► Stitching
                                                          │
                                           Bundling & Packing (final stage → finished boxes)
                                                          │
                              Box Quality Test (COA) ─► Delivery Note (bundles) ─► Sales Invoice
```

## 4. Modules

### Masters
| DocType | Purpose |
|---|---|
| **Flute Type** | Flute height, take-up factor (paper used per metre of board) |
| **Box Style** | Sheet formula: wrap-around (2L + 2W + glue flap; flap factors for RSC/HSC/FOL) or manual (trays, die-cut, pads) |
| **Production Stage** | Plant routing with sequence, which stage consumes reels, which books finished goods, and which uses die/plate |
| **Box Tooling** | Dies and printing plates: customer, rack, cost, expected life, impressions used (auto) |
| **Box Quality Parameter** | BS, BCT, ECT, GSM, moisture, Cobb, dimensions, visual checks |
| **Corrugation Settings** | All defaults: allowances, waste, conversion/printing/stitch/gum rates, deckles, warehouses, price lists |

### Sales & costing
* **Box Specification** – customer box master. Enter L × W × H, style, ply and flutes; layers are built
  automatically (Top Liner, Flute 1, Middle Liner …). Pick paper per layer and the system calculates
  sheet size, sheet size in inches, board GSM (with flute take-up), box weight, board caliper, theoretical
  BS, estimated BCT (McKee), gum per box, and the best standard reel deckle with outs and trim %.
  * **Ups per sheet** for small die-cut boxes: box weight, paper, gum and corrugator cuts are per box.
  * **Pricing basis Per Box / Per Kg**: the box item gets a Kg unit (1 kg = 1000 ÷ box weight boxes), so orders
    and invoices can be raised in Kg or Nos.
  * **Artwork approval** (version, status, approved on / by). Printing is blocked until it is Approved; a new
    artwork file resets the approval.
  * **Revisions**: changing size, ply, paper or ups after the BOM exists creates a new revision and BOM on save;
    open Work Orders keep the old BOM.
  Buttons: *Create Item & BOM*, *Box Costing*, *Deckle Options*. Prints **Box Job Card** with barcode.
* **Box Costing** – paper cost per layer from the paper price list, waste, conversion per kg, printing
  per colour, die/plate amortisation, stitching, gum, overhead, freight and mark-up. Shows cost and price
  per box and per kg. Submitting updates the customer price in the selling price list (Nos, and Kg for
  per-kg customers) and the spec. For per-kg customers enter the **agreed rate per kg**.
  **Margin approval**: below the minimum margin only the approver role can submit; the approver and time are recorded.
  Prints **Box Costing Sheet**.
* **Paper Price Revision** – enter new paper rates; the form lists every active box whose cost changes,
  with old/new cost and suggested new price at the same margin. On submit it updates paper prices and
  creates revised Box Costings as drafts – ready for the customer price-revision discussion. Customer prices change
  only when each revised costing is submitted (with margin approval if needed).
* **Quotation / Sales Order** – *Tools → Apply Box Costing Prices* pulls the latest costed price.

### Reels
* **Reel Inward** – gate entry of reels: paper, deckle (mm, inch auto), gross / core / net weight,
  moisture, supplier reel no. Reel numbers are auto-generated if left blank. On submit each reel becomes
  a **Batch** and a **Paper Reel**, and a Purchase Receipt (one row per reel, rate from the PO) is
  created. *Opening Stock* creates a stock receipt instead. *Print Reel Labels* prints 100 × 75 mm
  labels with Code-128 barcodes.
  **Weight shortage**: enter the mill / invoice weight per reel; shortage beyond the tolerance is valued and
  *Create → Shortage Debit Note* makes a draft debit note against the supplier's Purchase Invoice.
* **Reel Slitting** – cut a wide reel into narrower reels (e.g. 72" → 2 × 36"). Weights are split by width, the
  edge trim goes to scrap, each new reel gets its own number (`parent/1`, `parent/2`), batch and label.
  Partial cuts leave the rest on the original reel.
* **Paper Reel** – live balance weight, consumed weight, status (In Stock / Partially Used / Consumed / Returned),
  quality status, warehouse and rack. Balances follow the stock ledger automatically. A reel that failed the
  incoming test cannot be used or cut. *Create → Return to Supplier* makes a draft Purchase Return for its balance.
* **Reel Stock Audit** – scan reels with a barcode gun or the phone camera; the audit lists found,
  wrong-location, not-in-system and **missing** reels and the weight difference.

### Production
* **Deckle Plan** – put one or more work orders side by side on a reel width; *Suggest Best Deckle*
  ranks standard deckles by trim %. Saving as *Planned* writes deckle and outs back to the Work Orders.
* **Production Entry** – one entry per stage, shift and machine: operator, time, good and rejected
  quantity, output per hour, die/plate used and waste by type.
  * **Corrugation** stage: enter reels used with their balance weight; consumption is transferred to the
    Work Order WIP warehouse batch-wise.
  * **Printing / Die Cutting**: impressions are added to the plate/die, with a warning at 90 % of life.
  * **Bundling & Packing** (final): creates the finished-goods (Manufacture) entry, as draft by default.
  * Output is counted in **sheets** (corrugation to printing) or **boxes**; *box equivalent* = sheets × ups, so
    stages can be compared and WIP is right for multi-up jobs.
  * **Downtime** table (breakdown, power cut, no paper, changeover …): running hours, output per running hour
    and availability % are calculated.
  * **Other materials used** (gum, ink, wire): actual quantities are transferred and consumed instead of the BOM standard.
  * **Contract labour**: contractor, piece rate per stage, amount.
  * Waste kg can be booked automatically into scrap stock for sale.
  * *Create → Next Stage Entry* carries the work order forward.
* **Shop Floor Entry** (page) – the same entry on one simple phone / tablet screen: pick or scan the Work
  Order, tap the stage, scan reels and type the balance weight, enter output, waste and stoppages, Save.

### Quality & dispatch
* **Box Quality Test** – incoming paper (GSM ± tolerance, BF, moisture, Cobb), in-process and final
  inspection (dimensions ± tolerance, board GSM, BS, BCT, ECT, moisture, print, joint). Limits are filled
  from the spec; results evaluate automatically. Prints **Certificate of Analysis**. Incoming results
  are stamped on the reel.
* **Delivery Note** – boxes per bundle (from the spec) and number of bundles per line and in total.
  Prints **Box Delivery Challan** and **Box Bundle Label** (one label per bundle: customer part no, size,
  qty in bundle, bundle n of N, customer PO, barcode; the last bundle shows the remainder).
* **Box Complaint** – customer complaint register: type, severity, delivery / invoice / work order,
  *Trace Reels & Production* (which reels, suppliers and reel QC went into the job), root cause, corrective and
  preventive action, owner, target date, resolution and credit note. Cannot be closed without a resolution and action.

### Reports
| Report | Answers |
|---|---|
| Reel Stock Register | What reels do I have by GSM / BF / deckle, and how old are they? |
| Reel Consumption | Which reels went into which job, layer and machine? |
| Production Summary | Output, rejection %, output per hour by stage / machine / shift / operator |
| Waste Analysis | Waste by type, stage and machine, and as % of paper used |
| Paper Consumption Variance | Actual paper per work order vs standard box weight + waste |
| Box Price and Margin | Margin at costing time vs margin at today's paper prices |
| Paper Requirement Planning | Paper needed for open orders by GSM / BF / **deckle** vs reels in stock (same and wider deckle) and open POs; one click makes a Material Request |
| Box WIP by Stage | Where each open job is lying: boxes done per stage and quantity waiting after each stage |
| Job Profitability | Per Work Order: revenue, actual material, standard conversion, margin vs quoted margin, paper variance, waste, downtime |
| Downtime Analysis | Stoppage hours by reason / machine / stage / shift, share of shift time |
| Piece Rate Labour | Contract labour payable by contractor / operator and stage |
| Reel Weight Shortage | Shortage per inward, claimable kg and amount, claim status |

**Dashboards**: number cards for boxes packed today, paper used and waste today, waste % this month, paper stock
value, reels in stock / pending QC, open work orders, boxes below minimum margin, costings awaiting approval and
open complaints; charts for daily box output, paper used and waste.

## 5. Calculation notes

* Sheet length = 2L + 2W + glue flap (+ 4 × caliper when dimensions are *inner*)
* Sheet width (corrugator cut) = H + (top flap + bottom flap factor) × W (+ caliper allowances)
* Board GSM = Σ liner GSM + Σ (flute GSM × take-up factor); box weight = sheet area × board GSM
* Theoretical BS = Σ liner (BF × GSM / 1000) + ½ × Σ flute (BF × GSM / 1000) — quoting estimate only
* BCT (McKee) = 5.87 × ECT × √(caliper × perimeter); needs ECT from a lab test or the paper supplier
* Price = total cost × (1 + mark-up %); price per kg = price ÷ box weight

The engine lives in `corrugated_erp/utils/corrugation.py` (pure Python) with unit tests in
`corrugated_erp/tests/test_corrugation.py`:

```bash
python -m unittest corrugated_erp.tests.test_corrugation          # without a bench
bench --site <site> run-tests --module corrugated_erp.tests.test_corrugation
```

## 6. Setup guides for standard ERPNext features

| Need | How |
|---|---|
| Box + partitions + pads sold as one set | Make each part a Box Specification, then a **Product Bundle** with the set as parent item |
| Rework of rejected boxes | New Work Order for the same box with a "rework" BOM (no paper, only labour / tape), or book rework as a Production Entry at the relevant stage |
| Many paper qualities | Optional: **Item Variants** with attributes BF, GSM, Shade (keep *Is Kraft Paper*, GSM and BF filled on each variant) |
| ±10 % quantity tolerance on orders | Stock Settings → *Over Delivery/Receipt Allowance*, and Selling Settings / Item for over-billing |
| Monthly schedules / call-offs | **Blanket Order** for the agreed rate and quantity, Sales Orders against it with delivery dates |
| E-way bill, e-invoice, GST returns | Install the **India Compliance** app |
| Formal non-conformance / CAPA | Box Complaint covers customers; ERPNext **Non Conformance** (Quality module) for internal issues |

## 7. Permissions

Uses ERPNext's standard roles – no new role mapping is needed:
Sales User/Manager (specs, costing), Stock User/Manager (reel inward, reels, audit), Manufacturing
User/Manager (deckle plans, production entries, tooling), Quality Manager (tests), Purchase Manager
(paper price revision).

## 8. Known limits of this release

* Job work (outsourced printing/die-cutting) uses standard ERPNext Subcontracting.
* Machine / PLC counters are not connected; output is entered by the operator.
* Job Profitability uses actual material and **standard** conversion cost from the costing (not actual
  power and salaries per job).
* Slitting trim goes to scrap stock at zero value; its paper cost stays in the new reels.
* This release has been checked against the Frappe / ERPNext v15 and v16 source code and its calculation engine
  is unit tested, but it must be tested end to end on a trial site with your own data before go-live.
* If a reel's paper item is not in the Work Order BOM, enable *Allow Alternative Item* on the Work Order
  and maintain **Item Alternative** records, or update the BOM from the Box Specification.
