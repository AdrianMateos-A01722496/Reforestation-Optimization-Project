import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import pandas as pd

class DailyDataCollector:
    def __init__(self, start_date: datetime):
        self.start_date = start_date
        self.daily_data = {}
        
    def collect_day_data(self, state, day_number: int) -> Dict[str, Any]:
        """Collect comprehensive data for a single day"""
        current_date = self.start_date + timedelta(days=day_number)
        
        # Basic day info
        day_data = {
            "day_number": day_number,
            "date": current_date.strftime("%Y-%m-%d"),
            "weekday": current_date.strftime("%A"),
            "is_weekend": state.is_weekend(day_number),
            
            # Progress metrics
            "remaining_demand_total": int(state.remaining_demand.sum().sum()),
            "warehouse_inventory_total": int(state.get_total_warehouse_inventory()),
            "total_cost_so_far": float(state.total_cost),
            "labor_hours_used": float(6.0 - state.remaining_labor_hours),
            "remaining_labor_hours": float(state.remaining_labor_hours),
            
            # Detailed inventory by species (TOTAL across all stages)
            "warehouse_inventory_by_species": {
                str(i): int(
                    state.acclim_stage_0[i] + 
                    state.acclim_stage_1[i] + 
                    state.acclim_stage_2[i] + 
                    state.available_inventory[i]
                ) for i in range(1, 11)
            },
            
            # Detailed acclimation breakdown by species and stage
            "warehouse_detailed_by_stage": {
                "stage_0_arriving_today": {str(i): int(state.acclim_stage_0[i]) for i in range(1, 11)},
                "stage_1_one_day_old": {str(i): int(state.acclim_stage_1[i]) for i in range(1, 11)},
                "stage_2_two_days_old": {str(i): int(state.acclim_stage_2[i]) for i in range(1, 11)},
                "stage_3_ready_for_planting": {str(i): int(state.available_inventory[i]) for i in range(1, 11)}
            },
            
            # Acclimatization stages (kept for backward compatibility)
            "acclim_stage_0": {str(i): int(state.acclim_stage_0[i]) for i in range(1, 11)},
            "acclim_stage_1": {str(i): int(state.acclim_stage_1[i]) for i in range(1, 11)},
            "acclim_stage_2": {str(i): int(state.acclim_stage_2[i]) for i in range(1, 11)},
            
            # Daily activities
            "orders_placed": [],
            "orders_arrived": [],
            "planting_activities": [],
            "transportation_activities": [],
            
            # Polygons status
            "polygons_completed_today": [],
            "remaining_demand_by_polygon": {}
        }
        
        # Orders placed today
        for order in state.orders:
            if order.order_day == day_number:
                order_data = {
                    "provider": order.provider,
                    "total_plants": int(order.amount_of_plants),
                    "cost": float(order.cost),
                    "species_breakdown": {
                        str(species_id): int(quantity) 
                        for species_id, quantity in order.species_id_quantity
                    },
                    "arrival_day": int(order.arrival_day)
                }
                day_data["orders_placed"].append(order_data)
        
        # Orders that arrived today
        for order in state.orders:
            if order.arrival_day == day_number:
                arrival_data = {
                    "provider": order.provider,
                    "total_plants": int(order.amount_of_plants),
                    "cost": float(order.cost),
                    "species_breakdown": {
                        str(species_id): int(quantity) 
                        for species_id, quantity in order.species_id_quantity
                    },
                    "order_day": int(order.order_day)
                }
                day_data["orders_arrived"].append(arrival_data)
        
        # Planting activities today
        total_plants_planted_today = 0
        for planting in state.planting_activities:
            if planting.day == day_number:
                planting_data = {
                    "polygon_id": int(planting.polygon_id),
                    "species_id": int(planting.species_id),
                    "quantity": int(planting.quantity),
                    "cost": float(planting.planting_cost),
                    "treatment_time": float(planting.treatment_time),
                    "trip_number": int(getattr(planting, 'trip_number', 1))  # Default to 1 for backward compatibility
                }
                day_data["planting_activities"].append(planting_data)
                total_plants_planted_today += planting.quantity
        
        # Add total plants planted today for easy reference
        day_data["total_plants_planted_today"] = int(total_plants_planted_today)
        
        # Transportation activities today
        for transport in state.transportation_activities:
            if transport.day == day_number:
                transport_data = {
                    "from_polygon": int(transport.from_polygon),
                    "to_polygon": int(transport.to_polygon),
                    "species_id": int(transport.species_id),
                    "quantity": int(transport.quantity),
                    "travel_time": float(transport.travel_time),
                    "load_time": float(transport.load_time),
                    "unload_time": float(transport.unload_time)
                }
                day_data["transportation_activities"].append(transport_data)
        
        # Remaining demand by polygon (only for polygons with demand > 0)
        for polygon_id in state.remaining_demand.index:
            polygon_demand = int(state.remaining_demand.loc[polygon_id].sum())
            if polygon_demand > 0:
                day_data["remaining_demand_by_polygon"][str(polygon_id)] = polygon_demand
        
        # Calculate completion percentage
        initial_demand = 95588  # Total initial demand
        completion_percentage = ((initial_demand - day_data["remaining_demand_total"]) / initial_demand) * 100
        day_data["completion_percentage"] = round(completion_percentage, 2)
        
        # Daily costs breakdown
        daily_order_cost = sum(order["cost"] for order in day_data["orders_placed"])
        daily_planting_cost = sum(plant["cost"] for plant in day_data["planting_activities"])
        day_data["daily_costs"] = {
            "orders": float(daily_order_cost),
            "planting": float(daily_planting_cost),
            "total": float(daily_order_cost + daily_planting_cost)
        }
        
        # Store the day's data
        self.daily_data[str(day_number)] = day_data
        return day_data
    
    def save_to_json(self, filename: str = "reforestation_daily_data.json"):
        """Save all collected data to JSON file"""
        
        # Add summary information
        summary = {
            "project_summary": {
                "start_date": self.start_date.strftime("%Y-%m-%d"),
                "total_days": len(self.daily_data),
                "initial_demand": 95588,
                "final_completion": 100.0,
                "total_cost": max(day["total_cost_so_far"] for day in self.daily_data.values()) if self.daily_data else 0
            },
            "daily_data": self.daily_data
        }
        
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"✅ Daily data saved to {filename}")
        return filename
        
    def get_completion_timeline(self) -> List[Dict]:
        """Get a timeline of major milestones"""
        milestones = []
        
        for day_str, day_data in self.daily_data.items():
            completion = day_data["completion_percentage"]
            
            # Major milestones
            if completion >= 25 and not any(m["type"] == "25%" for m in milestones):
                milestones.append({
                    "day": int(day_str),
                    "date": day_data["date"],
                    "type": "25%",
                    "description": "25% completion milestone reached"
                })
            elif completion >= 50 and not any(m["type"] == "50%" for m in milestones):
                milestones.append({
                    "day": int(day_str),
                    "date": day_data["date"],
                    "type": "50%",
                    "description": "50% completion milestone reached"
                })
            elif completion >= 75 and not any(m["type"] == "75%" for m in milestones):
                milestones.append({
                    "day": int(day_str),
                    "date": day_data["date"],
                    "type": "75%",
                    "description": "75% completion milestone reached"
                })
            elif completion >= 90 and not any(m["type"] == "90%" for m in milestones):
                milestones.append({
                    "day": int(day_str),
                    "date": day_data["date"],
                    "type": "90%",
                    "description": "90% completion milestone reached"
                })
        
        return milestones 