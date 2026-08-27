# Business Rules

## Purpose

Define the supply-chain logic used to transform demand, inventory, and in-transit supply into a finished-goods production recommendation.

The rules are designed around the Production Analyst's actual responsibility:

> Analyze existing demand and available supply, determine the required production quantity, and prepare the quantities to communicate to Contract Manufacturers.

The automation does NOT create demand.

---

# 1. Core Planning Logic

The production recommendation is based on:

- Demand
- Applicable on-hand inventory
- In-transit supply
- Safety-stock requirement
- Product status
- MOQ / production multiple
- Market and location rules
- Product/pack configuration

Conceptually:

Demand
- Available Supply
- Required Safety Stock
= Net Production Requirement

Where:

Available Supply =
Applicable On-Hand Inventory + Applicable In-Transit Supply

The exact monthly inventory roll-forward logic will be defined during implementation.

---

# 2. Demand Is an Input

Demand comes from the Sales demand file.

The automation must NOT:

- Modify demand
- Forecast demand
- Override Sales demand
- Generate demand

The Production Planning workflow consumes the demand provided by Sales.

---

# 3. Monthly Planning Horizon

The FG planning file contains a monthly planning horizon.

Example:

| SKU | Metric | Sep | Oct | Nov | Dec | Jan | Feb |
|---|---|---:|---:|---:|---:|---:|---:|
| SKU-001 | Demand | 500 | 600 | 700 | 650 | 800 | 900 |
| SKU-001 | Inventory | 1,200 | | | | | |
| SKU-001 | In Transit | 500 | 0 | 0 | 0 | 0 | 0 |
| SKU-001 | Safety | TBD | TBD | TBD | TBD | TBD | TBD |
| SKU-001 | Total Prod | Calculated | Calculated | Calculated | Calculated | Calculated | Calculated |

The production recommendation must consider the planning horizon rather than looking only at the current month.

---

# 4. Inventory Location Rule

Inventory must be evaluated according to the SKU's applicable market/location.

A SKU's inventory cannot automatically be treated as globally available.

Examples:

EU SKU → EU inventory
CA SKU → Canada inventory
US SKU → US inventory

Some SKUs may not contain an explicit market designation.

For those SKUs, the SKU Master must contain the applicable location rule.

If the workflow cannot determine which inventory location applies:

→ Do not silently calculate production.

→ Create a planner exception.

---

# 5. SKU and Market Identification

The SKU Master is the source of truth for interpreting SKU characteristics.

Relevant attributes include:

- Market
- Product Type
- Product Category
- Pack Type
- Units per Pack
- Product Status
- Manufacturer
- Manufacturing Site
- MOQ
- Location Rule

This prevents market/location and SKU-specific rules from being embedded throughout the workflow.

---

# 6. Discontinued SKU Rule

A discontinued SKU must not receive a new production recommendation.

If:

Status = Discontinued

Then:

Production Recommendation = 0

However, if a discontinued SKU has active demand:

→ Flag the SKU as a planner exception.

Example:

DISCONTINUED SKU + DEMAND > 0
→ Production = 0
→ Exception = "Discontinued SKU has demand"

The workflow must NOT silently delete the demand.

This allows the planner to investigate whether:

- Demand is incorrect
- The SKU was incorrectly discontinued
- A replacement SKU should be used
- Existing inventory should satisfy the demand

---

# 7. New SKU Rule

A SKU appearing in the demand file but missing from the SKU Master must be treated as an exception.

Do not automatically create a production recommendation.

Exception:

"New / Unknown SKU requires master-data validation"

This prevents a new SKU from being missed simply because it was not added to the planning logic.

---

# 8. Pack Configuration

Finished-good SKUs may represent different selling configurations.

Examples:

- Single
- Twin Pack
- 3-Pack
- 4-Pack
- Costco Bundle
- Kit Package

The SKU Master should contain:

Pack Type
Units per Pack

Example:

| SKU | Pack Type | Units per Pack |
|---|---|---:|
| CAM-A | Single | 1 |
| CAM-B | Twin | 2 |
| CAM-C | 3-Pack | 3 |
| CAM-D | 4-Pack | 4 |

Where required, the workflow can calculate underlying camera/unit demand.

Example:

Twin Pack demand = 500 packs

Underlying units =

500 × 2 = 1,000 units

The workflow must preserve the original SKU-level demand while allowing unit-level calculations where required.

---

# 9. Costco Bundles

Costco bundles are treated as distinct product configurations.

They should not automatically be treated as standard camera SKUs.

Their demand and unit conversion must be interpreted through the SKU Master.

If a Costco bundle has a unique configuration:

→ SKU Master defines the configuration.

Do not create bundle-specific logic directly inside the main workflow.

---

# 10. Kit Packages

Kit packages may have a different BOM and component structure.

For the first version of the FG workflow:

Kit Package = Finished Good

The FG workflow determines the required quantity of the kit package.

Component/BOM explosion is a later stage.

The production-planning workflow should therefore NOT calculate components at this stage.

---

# 11. Manufacturing Site

Each SKU should identify the applicable manufacturing source.

Example:

Manufacturer / Manufacturing Site:
- China
- India

This information will later determine which Contract Manufacturer receives the production requirement.

The FG calculation should remain independent of the CM communication format.

---

# 12. MOQ / Production Multiple

The current planning assumption is:

China MOQ / production multiple = 500
India MOQ / production multiple = 500

Production recommendations should therefore be rounded to the applicable production multiple.

Example:

Calculated requirement = 620

Production recommendation = 1,000

Calculated requirement = 480

Production recommendation = 500

Calculated requirement = 1,120

Production recommendation = 1,500

The exact rounding rule must be confirmed against the actual Vosker production practice.

---

# 13. Low-Demand Production Rule

A production quantity that is technically required may still be commercially inefficient.

Example:

Demand = 50
MOQ = 500

The workflow should not automatically assume that producing 500 is always the correct business decision.

Instead:

→ Calculate the MOQ-based requirement.

→ Identify low-demand / MOQ mismatch.

→ Create a planner decision flag.

Example:

"Demand below MOQ — planner review required"

The planner may determine that production is not worthwhile and that another action is required.

This is a HUMAN decision unless a formally approved business rule is later defined.

---

# 14. Safety Stock

Safety stock is NOT an external input in the first version.

In the previous planning process, safety stock was calculated inside the FG planning file using Excel formulas.

The exact historical formula is currently unknown.

Therefore:

Safety Stock Formula = TBD

The automation should not invent a replacement formula.

Once the historical formula or business requirement is confirmed, it will be documented here.

Potential future approaches may include:

- Percentage of demand
- Demand variability
- Lead-time based safety stock
- Service-level based safety stock
- SKU-specific policy

The selected method must be a business decision, not an arbitrary automation decision.

---

# 15. Inventory Consumption Across Months

The planning horizon must account for the fact that inventory available today is consumed by future demand.

The workflow should eventually calculate a projected supply position across the planning horizon.

Conceptually:

Opening Supply
+ Scheduled Inbound
+ Planned Production
- Demand
- Required Safety Stock
= Projected Ending Supply

The exact treatment of planned production timing and in-transit arrival month must be defined during implementation.

This is important because simply subtracting the same current inventory from every monthly demand value would produce an incorrect planning result.

---

# 16. In-Transit Timing

In-transit supply must be associated with the appropriate destination and expected arrival period where that information is available.

Example:

500 units arriving in October

should not automatically be treated as supply available in September.

The planning logic should therefore consider:

SKU
+ Destination
+ Quantity
+ Expected Arrival

If arrival timing is unavailable:

→ Flag the record for review rather than making an unsafe assumption.

---

# 17. Supply Shortage / Production Requirement

For each SKU and planning period, the workflow should identify whether available supply is sufficient to cover demand and required safety stock.

If projected supply is sufficient:

→ Production may be 0.

If projected supply is insufficient:

→ Calculate the net production requirement.

Then apply the applicable production multiple / MOQ.

---

# 18. Production Quantity Must Be Explainable

The workflow should not simply output:

Production = 1,000

It should also retain the underlying drivers.

Example:

| SKU | Demand | On Hand | In Transit | Safety | Net Requirement | MOQ | Recommended Production |
|---|---:|---:|---:|---:|---:|---:|---:|
| CAM-001-EU | 1,200 | 500 | 0 | 100 | 800 | 500 | 1,000 |

This allows a planner to understand WHY the recommendation was generated.

---

# 19. Planner Exceptions

The automation should generate a separate exception view for situations requiring human attention.

Examples:

- Discontinued SKU with demand
- New SKU not in SKU Master
- Unknown SKU
- Missing location mapping
- Conflicting market/location
- Missing inventory
- Missing in-transit destination
- Missing arrival date where required
- Demand below MOQ
- Unusually high production recommendation
- SKU with unusual supply/demand situation

The goal is:

> Automate the calculation.  
> Surface the uncertainty.  
> Keep the planner responsible for judgment.

---

# 20. Production Recommendation vs Planner Decision

The workflow produces a recommendation.

It does not blindly convert every mathematical result into a production commitment.

Example:

System:

"Recommended production = 500"

Planner:

"Do not produce — demand is too low and SKU may be phased out."

The planner decision should be captured as an intervention/comment where appropriate.

---

# 21. Business Rule Priority

Rules should be evaluated in a controlled sequence.

Recommended order:

1. Validate SKU
2. Validate SKU Master mapping
3. Determine market/location
4. Determine applicable inventory
5. Determine applicable in-transit supply
6. Check product status
7. Calculate supply position
8. Apply safety-stock requirement
9. Calculate net production requirement
10. Apply MOQ / production multiple
11. Identify low-demand / MOQ exceptions
12. Produce planner recommendation
13. Produce planner exceptions

---

# 22. AI Boundary

The core production calculation should be deterministic.

AI should NOT decide:

- How much demand exists
- Which inventory location applies when a defined master-data rule exists
- Whether a SKU is discontinued
- The mathematical production requirement
- MOQ rounding
- BOM quantities

AI may be considered later for tasks such as:

- Explaining unusual exceptions
- Prioritizing planner attention
- Summarizing multiple exceptions
- Interpreting unstructured supplier/customer communication
- Identifying patterns across historical planning decisions

AI is an enhancement to the planning process, not the source of truth for deterministic calculations.

---

# 23. Future BOM / Component Planning

The first release ends at finished-goods production planning.

Future stage:

FG Production Requirement
↓
BOM
↓
Component Requirement
↓
Component Supply / Inventory
↓
Component Production / Purchase Requirement

This will be implemented separately.

The BOM should therefore NOT complicate the initial FG workflow.

---

# 24. Key Design Principle

The automation replaces repetitive spreadsheet manipulation, not supply-chain judgment.

The intended operating model is:

SOURCE DATA
↓
VALIDATE
↓
NORMALIZE
↓
APPLY BUSINESS RULES
↓
CALCULATE FG REQUIREMENT
↓
FLAG EXCEPTIONS
↓
PLANNER REVIEW
↓
CM COMMUNICATION

The system should make the Production Analyst faster and more reliable without hiding the reasoning behind the recommendation.
