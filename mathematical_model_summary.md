# Mathematical Model for Reforestation Supply Chain Optimization

## 1. Overall Goal

The objective is to create an optimal schedule for a reforestation project. This involves ordering 10 different plant species from 3 providers, managing them in a central warehouse (Polygon 18), and planting them across 30 different polygons. The goal is to fulfill the specific demand of each polygon while minimizing total costs and/or the total project duration, subject to logistical, inventory, and operational constraints.

## 2. Key Assumptions & Simplifications

- **Acclimatization:** Plants require a minimum of 3 full days of acclimatization in the warehouse after arrival before they can be planted. There is **no maximum** time limit; once acclimatized, they remain available indefinitely.
- **Internal Transport:** Trips from the warehouse (P18) to the planting polygons are direct round trips (P18 $\leftrightarrow$ P). There is no monetary cost associated with these trips; their "cost" is the time they consume from the daily work schedule.
- **Nursery Orders:**
  - A maximum of one order per day can be placed with each provider.
  - Orders have a 1-day lead time (plants arrive the day after the order is placed).
  - The transport cost from the nursery is a per-plant fee ($0.5625 MXN/plant), not a fixed cost per order.
- **Work Schedule:** Planting and related operations (treatment, transport) only occur on weekdays (Monday-Friday). Plant arrivals to the warehouse (p18) and acclimatization still occur on weekends.
- **Planting Operations:** There is no separate "planting time" variable. This activity is considered part of the overall daily operations which include treatment, loading, travel, and unloading.
- **Warehouse (Polygon 18):** Polygon 18 is used exclusively as a central warehouse and has no planting demand.

## 3. Mathematical Model Components

### 3.1. Sets and Indices

- `P`: Set of all polygons, $p \in \{1, ..., 31\}$.
- `P_siembra`: Subset of planting polygons, $p \in P \setminus \{18\}$.
- `E`: Set of plant species, $e \in \{1, ..., 10\}$.
- `V`: Set of nurseries, $v \in \{\text{Moctezuma, Venado, Laguna Seca}\}$.
- `T`: Set of time periods (days), $t \in \{1, ..., T_{\text{max}}\}$.
- `D_aclim`: Set of acclimatization stages, $d \in \{0, 1, 2\}$. Represents the number of full days a plant has been acclimatizing.

---

### 3.2. Parameters

- `D_p,e`: Demand for species `e` in polygon `p`. (Data from demand table).
- `Cap_almacen`: Maximum plant capacity of the warehouse (10,000).
- `Cap_camioneta`: Maximum plant capacity of the internal transport vehicle (524).
- `Max_pedido_vivero`: Maximum number of plants per order from a nursery (8,000).
- `C_plantacion`: Monetary cost to plant a single plant ($20).
- `C_compra_e,v`: Monetary cost to purchase one plant of species `e` from nursery `v`.
- `C_transporte_planta_vivero`: Monetary cost for nursery transport per plant ($0.5625).
- `T_entrega_vivero`: Lead time for nursery orders in days (1).
- `T_aclim_min`: Minimum required acclimatization days (3).
- `T_tratamiento_e`: Time in hours for pre-plantation treatment for a plant of species `e`.
- `T_carga_descarga_planta`: Time in hours to load one plant AND unload it (`2 * (0.5 / 524)`).
- `T_viaje_p1,p2`: Time in hours for a one-way trip between polygon `p1` and `p2`.
- `H_jornada`: Effective work hours available per workday (6).
- `DiaLaborable_t`: Binary parameter. `1` if day `t` is a workday (Mon-Fri), `0` if it is a weekend (Sat-Sun).
- `M`: A large positive number (for "big-M" formulations).

---

### 3.3. Decision Variables

- `X_e,v,t`: (Integer >= 0) Quantity of species `e` ordered from nursery `v` on day `t`.
- `Y_v,t`: (Binary) `1` if an order is placed to nursery `v` on day `t`, `0` otherwise. (Needed to enforce the one-order-per-day rule and the max quantity per order).
- `InvAclim_e,d,t`: (Integer >= 0) Inventory of species `e` in acclimatization stage `d` at the end of day `t`.
- `InvDisp_e,t`: (Integer >= 0) Inventory of species `e` available for planting at the end of day `t`.
- `S_e,p,t`: (Integer >= 0) Quantity of species `e` sent to planting polygon `p` on day `t`.
- `N_viajes_p,t`: (Integer >= 0) Number of round trips made to planting polygon `p` on day `t`.
- `Plantado_e,p,t`: (Integer >= 0) Quantity of species `e` planted in polygon `p` on day `t`.
- `T_final`: (Integer >= 0) The final day of the project on which any activity occurs.

---

## 4. Objective Function

The primary objective is to minimize total cost. A secondary objective is to minimize total project duration.

**Objective 1: Minimize Total Cost ($Z_{costo}$)**

$$
\min Z_{\text{costo}} = \sum_{t \in T} \sum_{v \in V} \sum_{e \in E} X_{e,v,t} \cdot (C_{compra_{e,v}} + C_{transporte\_planta\_vivero}) + \sum_{t \in T} \sum_{p \in P_{siembra}} \sum_{e \in E} (Plantado_{e,p,t} \cdot C_{\text{plantacion}})
$$

* **Explanation:** The total cost is the sum of two components:
  1. The total purchase cost for all plants from all nurseries, which includes the per-plant material cost and the per-plant transport cost from the nursery.
  2. The total cost for planting all plants in their final destination polygons.

**Objective 2: Minimize Project Duration ($Z_{tiempo}$)**

$$
\min Z_{\text{tiempo}} = T_{\text{final}}
$$

* **Explanation:** This objective seeks to find the plan that completes all planting in the fewest number of days.

---

## 5. Constraints

#### A. Nursery Orders & Arrivals

**1. Max Quantity per Order:** An order placed with a nursery on a given day cannot exceed the maximum quantity. The binary variable `Y_v,t` models the "one order per day per provider" rule.

$$
\sum_{e \in E} X_{e,v,t} \le Max_{\text{pedido\_vivero}} \cdot Y_{v,t} \quad \forall v \in V, \forall t \in T
$$

> This ensures that if Y_v,t is 0 (no order), then X_e,v,t must be 0. If Y_v,t is 1 (order placed), the sum of plants can be up to Max_pedido_vivero.

#### B. Inventory Flow & Acclimatization

**2. Plant Arrivals & Start of Acclimatization:** Plants ordered on day `t - T_entrega_vivero` arrive today and enter the first stage (`d=0`) of acclimatization.

$$
InvAclim_{e,0,t} = \sum_{v \in V} X_{e,v, t-T_{\text{entrega\_vivero}}} \quad \forall e \in E, \forall t \ge T_{\text{entrega\_vivero}}
$$

> This links nursery orders to the start of the inventory process.

**3. Acclimatization Flow:** Plants move from one acclimatization stage to the next each day.

$$
InvAclim_{e,d,t} = InvAclim_{e,d-1,t-1} \quad \forall e \in E, \forall d \in \{1, 2\}, \forall t \ge 1
$$

> This constraint models the "aging" of plants through the acclimatization process.

**4. Available Inventory Balance:** The stock of ready-to-plant trees is updated daily based on plants completing acclimatization and plants being shipped out for planting.

$$
InvDisp_{e,t} = InvDisp_{e,t-1} + InvAclim_{e,2,t-1} - \sum_{p \in P_{siembra}} S_{e,p,t} \quad \forall e \in E, \forall t \ge 1
$$

> This is the main inventory balance equation for plants that are ready to be used. `InvAclim_e,2,t-1` represents the plants that completed their 3rd day of acclimatization yesterday.

#### C. Capacity Constraints

**5. Warehouse Capacity:** The total number of plants in the warehouse (in any state) cannot exceed the maximum capacity.

$$
\sum_{e \in E} \left( InvDisp_{e,t} + \sum_{d \in D_{aclim}} InvAclim_{e,d,t} \right) \le Cap_{almacen} \quad \forall t \in T
$$

> This sums up all plants of all species, both available and in acclimatization, on any given day.

#### D. Planting & Demand Constraints

**6. Demand Fulfillment:** The total number of plants of each species planted in each polygon must equal its specific demand by the end of the project.

$$
\sum_{t \in T} Plantado_{e,p,t} = D_{p,e} \quad \forall e \in E, \forall p \in P_{siembra}
$$

> This is the core goal of the reforestation effort.

**7. Planting Logic:** Plants sent to a polygon are considered planted on the same day.

$$
Plantado_{e,p,t} = S_{e,p,t} \quad \forall e \in E, \forall p \in P_{siembra}, \forall t \in T
$$

> This links the logistics variable S with the goal-oriented variable Plantado.

#### E. Operational & Daily Work Constraints

**8. Internal Transport Capacity:** The total number of plants sent to a polygon in a day cannot exceed the capacity of the trips made.

$$
\sum_{e \in E} S_{e,p,t} \le N_{viajes_{p,t}} \cdot Cap_{camioneta} \quad \forall p \in P_{siembra}, \forall t \in T
$$

> This ensures enough truck trips are scheduled for the planned shipments.

**9. Workday Restriction (No Weekends):** Shipments and trips for planting can only occur on designated workdays.

$$
S_{e,p,t} \le M \cdot DiaLaborable_t \quad \forall e \in E, \forall p \in P_{siembra}, \forall t \in T
$$

> If DiaLaborable_t is 0 (weekend), S_e,p,t must be 0. M is a large number.

$$
N_{viajes_{p,t}} \le M \cdot DiaLaborable_t \quad \forall p \in P_{siembra}, \forall t \in T
$$

> Similarly, no trips are made on non-workdays.

**10. Daily Work Hour Limit:** On any given workday, the sum of time for all operational activities cannot exceed the available work hours.

$$
\sum_{p \in P_{siembra}} \left( \sum_{e \in E} S_{e,p,t} \cdot T_{\text{tratamiento}_e} \right) + \sum_{p \in P_{siembra}} \left( \sum_{e \in E} S_{e,p,t} \cdot 2 \cdot T_{\text{carga\_descarga\_planta}} \right) + \sum_{p \in P_{siembra}} \left( N_{viajes_{p,t}} \cdot 2 \cdot T_{\text{viaje}_{18,p}} \right) \le H_{\text{jornada}} \quad \forall t \text{ s.t. } DiaLaborable_t = 1
$$

> This constraint is the daily scheduling bottleneck. It sums the time for treatment, loading/unloading (T_carga_descarga_planta includes both), and round-trip travel time for all activities planned for a given workday.
