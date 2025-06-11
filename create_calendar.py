import json
from datetime import datetime, timedelta
import os

def create_interactive_calendar(json_file="reforestation_daily_data.json", 
                              output_file="reforestation_calendar.html"):
    """Create a beautiful interactive HTML calendar from the daily data"""
    
    # Load the JSON data
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    project_summary = data["project_summary"]
    daily_data = data["daily_data"]
    
    # Generate the HTML content
    html_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reforestation Project Calendar - Interactive Timeline</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .header {{
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        .header .subtitle {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
            max-width: 1200px;
            margin: 0 auto 30px auto;
        }}
        
        .summary-card {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }}
        
        .summary-card h3 {{
            color: #333;
            margin-bottom: 10px;
        }}
        
        .summary-card .value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .calendar-container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.1);
        }}
        
        .calendar-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        
        .day-cell {{
            aspect-ratio: 1;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
            padding: 10px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            border: 2px solid transparent;
            position: relative;
            overflow: hidden;
        }}
        
        .day-cell:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.2);
            border-color: #667eea;
        }}
        
        .day-number {{
            font-weight: bold;
            font-size: 1.1em;
        }}
        
        .day-date {{
            font-size: 0.8em;
            opacity: 0.7;
        }}
        
        .completion-bar {{
            position: absolute;
            bottom: 0;
            left: 0;
            height: 4px;
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
            transition: width 0.3s ease;
        }}
        
        .day-activity {{
            font-size: 0.7em;
            margin-top: 5px;
        }}
        
        /* Different colors based on completion percentage */
        .completion-0-25 {{ background: linear-gradient(135deg, #ffebee, #ffcdd2); }}
        .completion-25-50 {{ background: linear-gradient(135deg, #fff3e0, #ffcc02); }}
        .completion-50-75 {{ background: linear-gradient(135deg, #e8f5e8, #a5d6a7); }}
        .completion-75-100 {{ background: linear-gradient(135deg, #e1f5fe, #4fc3f7); }}
        .completion-100 {{ background: linear-gradient(135deg, #c8e6c9, #4caf50); }}
        
        .weekend {{
            opacity: 0.6;
            background: linear-gradient(135deg, #f3e5f5, #ce93d8) !important;
        }}
        
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.7);
            backdrop-filter: blur(5px);
        }}
        
        .modal-content {{
            background-color: white;
            margin: 2% auto;
            padding: 0;
            border-radius: 20px;
            width: 90%;
            max-width: 800px;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 25px 50px rgba(0,0,0,0.3);
        }}
        
        .modal-header {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 20px 30px;
            border-radius: 20px 20px 0 0;
        }}
        
        .modal-body {{
            padding: 30px;
        }}
        
        .close {{
            color: white;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            opacity: 0.8;
        }}
        
        .close:hover {{
            opacity: 1;
        }}
        
        .detail-section {{
            margin-bottom: 25px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 12px;
            border-left: 4px solid #667eea;
        }}
        
        .detail-section h4 {{
            color: #333;
            margin-bottom: 15px;
            font-size: 1.2em;
        }}
        
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        
        .metric {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}
        
        .metric-value {{
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .metric-label {{
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        
        th {{
            background: #667eea;
            color: white;
            font-weight: 600;
        }}
        
        tr:hover {{
            background-color: #f5f5f5;
        }}
        
        .species-inventory {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 10px;
            margin-top: 10px;
        }}
        
        .species-item {{
            background: white;
            padding: 10px;
            border-radius: 6px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}
        
        .legend {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
        }}
        
        /* Species Legend Styles */
        .species-legend-toggle {{
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 999;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 12px 16px;
            border-radius: 12px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
        }}
        
        .species-legend-toggle:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }}
        
        .species-legend-panel {{
            position: fixed;
            top: 70px;
            left: 20px;
            z-index: 998;
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            max-width: 300px;
            display: none;
            border: 1px solid rgba(0,0,0,0.1);
        }}
        
        .species-legend-panel.show {{
            display: block;
        }}
        
        .species-legend-title {{
            font-size: 16px;
            font-weight: bold;
            color: #333;
            margin-bottom: 15px;
            text-align: center;
            border-bottom: 2px solid #667eea;
            padding-bottom: 8px;
        }}
        
        .species-legend-list {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        
        .species-legend-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px;
            background: #f8f9fa;
            border-radius: 8px;
            transition: background-color 0.2s ease;
        }}
        
        .species-legend-item:hover {{
            background: #e9ecef;
        }}
        
        .species-number {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
            flex-shrink: 0;
        }}
        
        .species-name {{
            font-size: 13px;
            color: #333;
            font-weight: 500;
            line-height: 1.3;
        }}
        
        @media (max-width: 768px) {{
            .calendar-grid {{
                grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
                gap: 8px;
            }}
            
            .day-cell {{
                padding: 6px;
            }}
            
            .summary-cards {{
                grid-template-columns: 1fr;
            }}
            
            .species-legend-toggle {{
                padding: 10px 12px;
                font-size: 12px;
            }}
            
            .species-legend-panel {{
                max-width: 250px;
                padding: 15px;
            }}
            
            .species-legend-title {{
                font-size: 14px;
            }}
            
            .species-name {{
                font-size: 12px;
            }}
        }}
    </style>
</head>
<body>
    <!-- Species Legend Toggle Button -->
    <button class="species-legend-toggle" onclick="toggleSpeciesLegend()">
        🌿 Species Guide
    </button>
    
    <!-- Species Legend Panel -->
    <div class="species-legend-panel" id="speciesLegendPanel">
        <div class="species-legend-title">Plant Species Reference</div>
        <div class="species-legend-list">
            <div class="species-legend-item">
                <div class="species-number">1</div>
                <div class="species-name">Agave lechuguilla</div>
            </div>
            <div class="species-legend-item">
                <div class="species-number">2</div>
                <div class="species-name">Agave salmiana</div>
            </div>
            <div class="species-legend-item">
                <div class="species-number">3</div>
                <div class="species-name">Agave scabra</div>
            </div>
            <div class="species-legend-item">
                <div class="species-number">4</div>
                <div class="species-name">Agave striata</div>
            </div>
            <div class="species-legend-item">
                <div class="species-number">5</div>
                <div class="species-name">Opuntia cantabrigiensis</div>
            </div>
            <div class="species-legend-item">
                <div class="species-number">6</div>
                <div class="species-name">Opuntia engelmani</div>
            </div>
            <div class="species-legend-item">
                <div class="species-number">7</div>
                <div class="species-name">Opuntia robusta</div>
            </div>
            <div class="species-legend-item">
                <div class="species-number">8</div>
                <div class="species-name">Opuntia streptacanta</div>
            </div>
            <div class="species-legend-item">
                <div class="species-number">9</div>
                <div class="species-name">Prosopis laevigata</div>
            </div>
            <div class="species-legend-item">
                <div class="species-number">10</div>
                <div class="species-name">Yucca filifera</div>
            </div>
        </div>
    </div>

    <div class="header">
        <h1>🌳 Reforestation Project Timeline</h1>
        <div class="subtitle">Interactive Daily Calendar - Click any day to see details</div>
    </div>
    
    <div class="summary-cards">
        <div class="summary-card">
            <h3>📅 Project Duration</h3>
            <div class="value">{project_summary['total_days']} days</div>
        </div>
        <div class="summary-card">
            <h3>🌱 Plants Planted</h3>
            <div class="value">{project_summary['initial_demand']:,}</div>
        </div>
        <div class="summary-card">
            <h3>💰 Total Cost</h3>
            <div class="value">${project_summary['total_cost']:,.0f}</div>
        </div>
        <div class="summary-card">
            <h3>🎯 Completion</h3>
            <div class="value">{project_summary['final_completion']}%</div>
        </div>
    </div>
    
    <div class="legend">
        <div class="legend-item">
            <div class="legend-color completion-0-25"></div>
            <span>0-25% Complete</span>
        </div>
        <div class="legend-item">
            <div class="legend-color completion-25-50"></div>
            <span>25-50% Complete</span>
        </div>
        <div class="legend-item">
            <div class="legend-color completion-50-75"></div>
            <span>50-75% Complete</span>
        </div>
        <div class="legend-item">
            <div class="legend-color completion-75-100"></div>
            <span>75-100% Complete</span>
        </div>
        <div class="legend-item">
            <div class="legend-color weekend"></div>
            <span>Weekend</span>
        </div>
        <div class="legend-item">
            <span>📦 Orders Created</span>
        </div>
        <div class="legend-item">
            <span>📥 Orders Arrived</span>
        </div>
        <div class="legend-item">
            <span>🌱 Plants Planted</span>
        </div>
    </div>
    
    <div class="calendar-container">
        <h2 style="text-align: center; color: #333; margin-bottom: 20px;">📅 Daily Progress Calendar</h2>
        <div class="calendar-grid" id="calendar">
            <!-- Calendar days will be generated by JavaScript -->
        </div>
    </div>
    
    <!-- Modal for day details -->
    <div id="dayModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <span class="close">&times;</span>
                <h2 id="modalTitle">Day Details</h2>
            </div>
            <div class="modal-body" id="modalBody">
                <!-- Day details will be populated by JavaScript -->
            </div>
        </div>
    </div>
    
    <script>
        // Daily data from Python
        const dailyData = {json.dumps(daily_data, indent=8)};
        const projectSummary = {json.dumps(project_summary, indent=8)};
        
        // Generate calendar
        function generateCalendar() {{
            const calendar = document.getElementById('calendar');
            
            Object.keys(dailyData).sort((a, b) => parseInt(a) - parseInt(b)).forEach(dayNumber => {{
                const day = dailyData[dayNumber];
                const dayCell = document.createElement('div');
                dayCell.className = 'day-cell';
                dayCell.onclick = () => showDayDetails(dayNumber);
                
                // Determine completion class
                const completion = day.completion_percentage;
                let completionClass = 'completion-0-25';
                if (completion >= 100) completionClass = 'completion-100';
                else if (completion >= 75) completionClass = 'completion-75-100';
                else if (completion >= 50) completionClass = 'completion-50-75';
                else if (completion >= 25) completionClass = 'completion-25-50';
                
                if (day.is_weekend) {{
                    dayCell.classList.add('weekend');
                }} else {{
                    dayCell.classList.add(completionClass);
                }}
                
                // Activity indicators
                let activities = [];
                if (day.orders_placed.length > 0) activities.push('📦');
                if (day.orders_arrived.length > 0) activities.push('📥');
                if (day.planting_activities.length > 0) activities.push('🌱');
                if (day.completion_percentage === 100) activities.push('🎉');
                
                dayCell.innerHTML = `
                    <div class="day-number">Day ${{day.day_number}}</div>
                    <div class="day-date">${{day.date}}</div>
                    <div class="day-activity">${{activities.join(' ')}}</div>
                    <div class="completion-bar" style="width: ${{completion}}%"></div>
                `;
                
                calendar.appendChild(dayCell);
            }});
        }}
        
        // Show day details in modal
        function showDayDetails(dayNumber) {{
            const day = dailyData[dayNumber];
            const modal = document.getElementById('dayModal');
            const modalTitle = document.getElementById('modalTitle');
            const modalBody = document.getElementById('modalBody');
            
            modalTitle.textContent = `Day ${{day.day_number}} - ${{day.date}} (${{day.weekday}})`;
            
            let modalContent = `
                <div class="detail-section">
                    <h4>📊 Progress Metrics</h4>
                    <div class="metric-grid">
                        <div class="metric">
                            <div class="metric-value">${{day.completion_percentage}}%</div>
                            <div class="metric-label">Completion</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${{day.remaining_demand_total.toLocaleString()}}</div>
                            <div class="metric-label">Remaining Plants</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${{day.warehouse_inventory_total.toLocaleString()}}</div>
                            <div class="metric-label">Warehouse Inventory</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${{(day.total_plants_planted_today || 0).toLocaleString()}}</div>
                            <div class="metric-label">Plants Planted Today</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${{day.labor_hours_used.toFixed(1)}}h</div>
                            <div class="metric-label">Labor Hours Used</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">$${{day.daily_costs.total.toLocaleString()}}</div>
                            <div class="metric-label">Daily Cost</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">$${{day.total_cost_so_far.toLocaleString()}}</div>
                            <div class="metric-label">Total Cost So Far</div>
                        </div>
                    </div>
                </div>
            `;
            
            // Orders placed today
            if (day.orders_placed.length > 0) {{
                modalContent += `
                    <div class="detail-section">
                        <h4>📦 Orders Created Today</h4>
                        <p style="color: #666; margin-bottom: 15px; font-style: italic;">Orders placed/created on this day (will arrive tomorrow)</p>
                        <table>
                            <thead>
                                <tr>
                                    <th>Provider</th>
                                    <th>Total Plants</th>
                                    <th>Cost</th>
                                    <th>Species Breakdown</th>
                                    <th>Will Arrive on Day</th>
                                </tr>
                            </thead>
                            <tbody>
                `;
                
                day.orders_placed.forEach(order => {{
                    const speciesBreakdown = Object.entries(order.species_breakdown)
                        .map(([species, qty]) => `S${{species}}:${{qty}}`)
                        .join(', ');
                    
                    modalContent += `
                        <tr>
                            <td>${{order.provider}}</td>
                            <td>${{order.total_plants.toLocaleString()}}</td>
                            <td>$${{order.cost.toLocaleString()}}</td>
                            <td>${{speciesBreakdown}}</td>
                            <td>Day ${{order.arrival_day}}</td>
                        </tr>
                    `;
                }});
                
                modalContent += `
                            </tbody>
                        </table>
                    </div>
                `;
            }}
            
            // Orders that arrived today
            if (day.orders_arrived && day.orders_arrived.length > 0) {{
                modalContent += `
                    <div class="detail-section">
                        <h4>📥 Orders Arrived Today</h4>
                        <p style="color: #666; margin-bottom: 15px; font-style: italic;">Orders that arrived today (previously created and now in warehouse)</p>
                        <table>
                            <thead>
                                <tr>
                                    <th>Provider</th>
                                    <th>Total Plants</th>
                                    <th>Cost</th>
                                    <th>Species Breakdown</th>
                                    <th>Originally Created on Day</th>
                                </tr>
                            </thead>
                            <tbody>
                `;
                
                day.orders_arrived.forEach(order => {{
                    const speciesBreakdown = Object.entries(order.species_breakdown)
                        .map(([species, qty]) => `S${{species}}:${{qty}}`)
                        .join(', ');
                    
                    modalContent += `
                        <tr>
                            <td>${{order.provider}}</td>
                            <td>${{order.total_plants.toLocaleString()}}</td>
                            <td>$${{order.cost.toLocaleString()}}</td>
                            <td>${{speciesBreakdown}}</td>
                            <td>Day ${{order.order_day}}</td>
                        </tr>
                    `;
                }});
                
                modalContent += `
                            </tbody>
                        </table>
                    </div>
                `;
            }}
            
            // Planting activities
            if (day.planting_activities.length > 0) {{
                // Group activities by trip number
                const tripGroups = {{}};
                day.planting_activities.forEach(activity => {{
                    const tripNum = activity.trip_number || 1;
                    if (!tripGroups[tripNum]) {{
                        tripGroups[tripNum] = [];
                    }}
                    tripGroups[tripNum].push(activity);
                }});
                
                modalContent += `
                    <div class="detail-section">
                        <h4>🌱 Planting Activities (Grouped by Trip)</h4>
                        <p style="color: #666; margin-bottom: 15px; font-style: italic;">
                            Total trips made: ${{Object.keys(tripGroups).length}} | 
                            Total plants planted: ${{day.planting_activities.reduce((sum, a) => sum + a.quantity, 0).toLocaleString()}}
                        </p>
                `;
                
                // Display each trip group
                Object.keys(tripGroups).sort((a, b) => parseInt(a) - parseInt(b)).forEach(tripNum => {{
                    const tripActivities = tripGroups[tripNum];
                    const tripTotal = tripActivities.reduce((sum, a) => sum + a.quantity, 0);
                    const tripCost = tripActivities.reduce((sum, a) => sum + a.cost, 0);
                    const tripPolygons = [...new Set(tripActivities.map(a => a.polygon_id))];
                    
                    modalContent += `
                        <div class="trip-section" style="margin-bottom: 20px; border: 1px solid #e0e0e0; border-radius: 8px; padding: 15px; background-color: #f9f9f9;">
                            <h5 style="margin: 0 0 10px 0; color: #2c5aa0;">
                                🚛 Trip ${{tripNum}} → Polygon(s): ${{tripPolygons.join(', ')}} | 
                                ${{tripTotal.toLocaleString()}} plants | 
                                $${{tripCost.toLocaleString()}} cost
                            </h5>
                            <table style="width: 100%; font-size: 0.9em;">
                                <thead>
                                    <tr style="background-color: #e8f0fe;">
                                        <th style="padding: 8px; text-align: left;">Polygon</th>
                                        <th style="padding: 8px; text-align: left;">Species</th>
                                        <th style="padding: 8px; text-align: right;">Quantity</th>
                                        <th style="padding: 8px; text-align: right;">Cost</th>
                                        <th style="padding: 8px; text-align: right;">Treatment Time</th>
                                    </tr>
                                </thead>
                                <tbody>
                    `;
                    
                    tripActivities.forEach(activity => {{
                        modalContent += `
                            <tr>
                                <td style="padding: 6px;">P${{activity.polygon_id}}</td>
                                <td style="padding: 6px;">Species ${{activity.species_id}}</td>
                                <td style="padding: 6px; text-align: right;">${{activity.quantity.toLocaleString()}}</td>
                                <td style="padding: 6px; text-align: right;">$${{activity.cost.toLocaleString()}}</td>
                                <td style="padding: 6px; text-align: right;">${{activity.treatment_time.toFixed(2)}}h</td>
                            </tr>
                        `;
                    }});
                    
                    modalContent += `
                                </tbody>
                            </table>
                        </div>
                    `;
                }});
                
                modalContent += `
                    </div>
                `;
            }}
            
            // Warehouse inventory by species
            modalContent += `
                <div class="detail-section">
                    <h4>🏭 Warehouse Inventory by Species</h4>
                    <div class="species-inventory">
            `;
            
            for (let i = 1; i <= 10; i++) {{
                const qty = day.warehouse_inventory_by_species[i.toString()] || 0;
                modalContent += `
                    <div class="species-item">
                        <div><strong>Species ${{i}}</strong></div>
                        <div>${{qty.toLocaleString()}} plants</div>
                    </div>
                `;
            }}
            
            modalContent += `
                    </div>
                </div>
            `;
            
            // Detailed warehouse breakdown by acclimation stage
            if (day.warehouse_detailed_by_stage) {{
                modalContent += `
                    <div class="detail-section">
                        <h4>🔄 Detailed Warehouse Breakdown by Acclimation Stage</h4>
                        <p style="color: #666; margin-bottom: 15px; font-style: italic;">
                            Plants must acclimate for 3 days before they can be planted
                        </p>
                `;
                
                const stages = [
                    {{ key: 'stage_0_arriving_today', label: '📥 Stage 0: Arriving Today (Day 0)', color: '#ffebee' }},
                    {{ key: 'stage_1_one_day_old', label: '⏳ Stage 1: One Day Old (Day 1)', color: '#fff3e0' }},
                    {{ key: 'stage_2_two_days_old', label: '⏰ Stage 2: Two Days Old (Day 2)', color: '#e8f5e8' }},
                    {{ key: 'stage_3_ready_for_planting', label: '✅ Stage 3: Ready for Planting (Day 3+)', color: '#e1f5fe' }}
                ];
                
                stages.forEach(stage => {{
                    const stageData = day.warehouse_detailed_by_stage[stage.key] || {{}};
                    const stageTotal = Object.values(stageData).reduce((sum, qty) => sum + qty, 0);
                    
                    if (stageTotal > 0) {{
                        modalContent += `
                            <div style="margin-bottom: 15px; padding: 15px; background-color: ${{stage.color}}; border-radius: 8px; border-left: 4px solid #667eea;">
                                <h5 style="margin: 0 0 10px 0; color: #333;">
                                    ${{stage.label}} - Total: ${{stageTotal.toLocaleString()}} plants
                                </h5>
                                <div class="species-inventory">
                        `;
                        
                        for (let i = 1; i <= 10; i++) {{
                            const qty = stageData[i.toString()] || 0;
                            if (qty > 0) {{
                                modalContent += `
                                    <div class="species-item" style="background-color: white; opacity: 0.9;">
                                        <div><strong>S${{i}}</strong></div>
                                        <div>${{qty.toLocaleString()}}</div>
                                    </div>
                                `;
                            }}
                        }}
                        
                        modalContent += `
                                </div>
                            </div>
                        `;
                    }}
                }});
                
                modalContent += `
                    </div>
                `;
            }}
            
            // Active polygons
            if (Object.keys(day.remaining_demand_by_polygon).length > 0) {{
                modalContent += `
                    <div class="detail-section">
                        <h4>🎯 Active Polygons (Remaining Demand)</h4>
                        <div class="metric-grid">
                `;
                
                Object.entries(day.remaining_demand_by_polygon).forEach(([polygon, demand]) => {{
                    modalContent += `
                        <div class="metric">
                            <div class="metric-value">${{demand.toLocaleString()}}</div>
                            <div class="metric-label">Polygon ${{polygon}}</div>
                        </div>
                    `;
                }});
                
                modalContent += `
                        </div>
                    </div>
                `;
            }}
            
            modalBody.innerHTML = modalContent;
            modal.style.display = 'block';
        }}
        
        // Species Legend Toggle Function
        function toggleSpeciesLegend() {{
            const panel = document.getElementById('speciesLegendPanel');
            panel.classList.toggle('show');
        }}
        
        // Close species legend when clicking outside
        document.addEventListener('click', function(event) {{
            const panel = document.getElementById('speciesLegendPanel');
            const toggle = document.querySelector('.species-legend-toggle');
            
            if (!panel.contains(event.target) && !toggle.contains(event.target)) {{
                panel.classList.remove('show');
            }}
        }});
        
        // Modal controls
        document.querySelector('.close').onclick = function() {{
            document.getElementById('dayModal').style.display = 'none';
        }}
        
        window.onclick = function(event) {{
            const modal = document.getElementById('dayModal');
            if (event.target === modal) {{
                modal.style.display = 'none';
            }}
        }}
        
        // Generate the calendar when page loads
        generateCalendar();
    </script>
</body>
</html>
    '''
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"🎨 Interactive calendar created: {output_file}")
    return output_file

if __name__ == "__main__":
    calendar_file = create_interactive_calendar()
    print(f"✅ Open {calendar_file} in your browser to view the interactive calendar!") 