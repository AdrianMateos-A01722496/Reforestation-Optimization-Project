import json
import pandas as pd

# Load the simulation data
with open('reforestation_daily_data.json', 'r') as f:
    data = json.load(f)

# Constants from utils.py
TRANSPORT_COST_PER_PLANT = 0.5625
PLANTATION_COST_PER_PLANT = 20.0

# Optimal provider costs
PROVIDER_COSTS = {
    "moctezuma": {3: 26, 4: 26, 5: 17, 7: 17, 9: 26.5, 10: 26},
    "venado": {4: 25, 5: 18, 6: 18, 7: 18, 8: 18},
    "laguna_seca": {1: 26, 2: 26, 3: 26, 6: 21, 7: 18}
}

# Optimal allocation (what we should be using)
OPTIMAL_COSTS = {
    1: 26,   # laguna_seca
    2: 26,   # laguna_seca  
    3: 26,   # laguna_seca
    4: 25,   # venado
    5: 17,   # moctezuma
    6: 18,   # venado
    7: 17,   # moctezuma
    8: 18,   # venado
    9: 26.5, # moctezuma
    10: 26   # moctezuma
}

print("🔍 COST ANALYSIS BREAKDOWN")
print("=" * 50)

# Analyze all orders placed during simulation
total_orders_cost = 0
total_plants_ordered = 0
total_transport_cost = 0
species_ordered = {i: 0 for i in range(1, 11)}
species_costs = {i: 0 for i in range(1, 11)}

daily_data = data['daily_data']

for day_key, day_data in daily_data.items():
    for order in day_data.get('orders_placed', []):
        order_cost = order['cost']
        total_orders_cost += order_cost
        
        # Break down each order
        for species_str, quantity in order['species_breakdown'].items():
            species_id = int(species_str)
            species_ordered[species_id] += quantity
            total_plants_ordered += quantity
            
            # Calculate actual cost breakdown
            provider = order['provider']
            plant_cost = quantity * PROVIDER_COSTS[provider][species_id]
            transport_cost = quantity * TRANSPORT_COST_PER_PLANT
            
            species_costs[species_id] += plant_cost
            total_transport_cost += transport_cost

# Calculate total planting costs
total_plants_planted = 0
total_planting_cost = 0

for day_key, day_data in daily_data.items():
    planting_cost = day_data['daily_costs']['planting']
    total_planting_cost += planting_cost
    total_plants_planted += day_data['total_plants_planted_today']

print(f"📊 SIMULATION TOTALS:")
print(f"Total plants ordered: {total_plants_ordered:,}")
print(f"Total plants planted: {total_plants_planted:,}")
print(f"Total orders cost: ${total_orders_cost:,.2f}")
print(f"Total planting cost: ${total_planting_cost:,.2f}")
print(f"Final total cost: ${data['project_summary']['total_cost']:,.2f}")
print()

print(f"🌱 PLANTS ORDERED BY SPECIES:")
for species_id in range(1, 11):
    quantity = species_ordered[species_id]
    cost = species_costs[species_id]
    optimal_cost = quantity * OPTIMAL_COSTS[species_id]
    print(f"Species {species_id}: {quantity:,} plants, ${cost:,.2f} (optimal: ${optimal_cost:,.2f})")

print()

# Calculate theoretical minimums
FINAL_DEMAND = {
    1: 6019, 2: 28642, 3: 6019, 4: 6019, 5: 7115,
    6: 5472, 7: 10580, 8: 9306, 9: 12587, 10: 3829
}

total_demand = sum(FINAL_DEMAND.values())
optimal_plant_costs = sum(FINAL_DEMAND[i] * OPTIMAL_COSTS[i] for i in range(1, 11))
optimal_transport_costs = total_demand * TRANSPORT_COST_PER_PLANT
optimal_planting_costs = total_demand * PLANTATION_COST_PER_PLANT

print(f"🎯 THEORETICAL OPTIMAL COSTS:")
print(f"Plant costs (optimal providers): ${optimal_plant_costs:,.2f}")
print(f"Transport costs: ${optimal_transport_costs:,.2f}")
print(f"Planting costs: ${optimal_planting_costs:,.2f}")
print(f"Total optimal: ${optimal_plant_costs + optimal_transport_costs + optimal_planting_costs:,.2f}")
print()

print(f"📈 COST COMPARISON:")
actual_plant_costs = sum(species_costs.values())
print(f"Actual plant costs: ${actual_plant_costs:,.2f}")
print(f"Optimal plant costs: ${optimal_plant_costs:,.2f}")
print(f"Plant cost difference: ${actual_plant_costs - optimal_plant_costs:,.2f} ({((actual_plant_costs / optimal_plant_costs) - 1) * 100:.1f}% higher)")
print()

print(f"Actual transport costs: ${total_transport_cost:,.2f}")
print(f"Optimal transport costs: ${optimal_transport_costs:,.2f}")
print(f"Transport cost difference: ${total_transport_cost - optimal_transport_costs:,.2f}")
print()

print(f"Total plants ordered vs needed: {total_plants_ordered:,} vs {total_demand:,}")
print(f"Excess plants ordered: {total_plants_ordered - total_demand:,} ({((total_plants_ordered / total_demand) - 1) * 100:.1f}% more)")
print()

# Check if we're using optimal providers
print(f"🔍 PROVIDER USAGE ANALYSIS:")
for day_key, day_data in daily_data.items():
    for order in day_data.get('orders_placed', []):
        provider = order['provider']
        for species_str, quantity in order['species_breakdown'].items():
            species_id = int(species_str)
            actual_cost = PROVIDER_COSTS[provider][species_id]
            optimal_cost = OPTIMAL_COSTS[species_id]
            if actual_cost != optimal_cost:
                print(f"⚠️  Day {day_key}: Species {species_id} from {provider} cost ${actual_cost} vs optimal ${optimal_cost}")
                break
    if int(day_key) > 10:  # Just check first few days
        break 