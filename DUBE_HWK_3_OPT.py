"""
Optimization question:
What is the least cost optimal mix of wind, solar, and energy storage system (ESS) to deliver a constant amount of power demand?  
"""

from __future__ import division
from pyomo.environ import *
from pyomo.opt import SolverFactory

## constants and assumptions
# capital costs for solar, and energy storage systems
solar_cap_cost 			= 800000000       # $/GW
ESS_p_cap_cost 			= 200000000       # $/GW
wind_cap_cost           = 1200000000      # $/GW
ESS_e_cap_cost 			= 150000000       # $/kGWh

# energy storage operational assumptions
ESS_min_level    		= 0.20      # %, minimum level of discharge of the battery
ESS_eta_c           	= 0.95      # ESS charging efficiency, looses 5% when charging
ESS_eta_d        		= 0.9       # ESS discharging efficiency, looses 10% when discharging
ESS_p_var_cost          = 5000     # ESS discharge cost $/GWh

curtailment_cost        = 1000     # curtailment penalty $/GWh


# create the model
model = AbstractModel(name = 'solar-storage model')

# create model sets
model.t                 = Set(initialize = [i for i in range(8760)], ordered=True)    
model.tech              = Set(initialize =['s_cap', 'w_cap', 'ESS_power_cap', 'ESS_energy_cap'], ordered=True)  


model.solar             = Param(model.t)
model.wind              = Param(model.t)
model.demand            = Param(model.t)
model.costs             = Param(model.tech, initialize={'s_cap' : solar_cap_cost, 'w_cap' : wind_cap_cost, 'ESS_power_cap' : ESS_p_cap_cost, 'ESS_energy_cap' : ESS_e_cap_cost})

## load data into parameters, solar and wind data are houlry capacity factor data
data = DataPortal()
data.load(filename = 'opt_model_data/2022_ERCOT_data.csv', select = ('t', 'solar', 'wind', 'demand'), param = (model.solar, model.wind, model.demand), index = (model.t))

## define variables
model.cap               = Var(model.tech, domain = NonNegativeReals)
model.ESS_SOC           = Var(model.t, domain = NonNegativeReals)
model.ESS_c             = Var(model.t, domain = NonNegativeReals)
model.ESS_d             = Var(model.t, domain = NonNegativeReals)
model.curt              = Var(model.t, domain = NonNegativeReals)

# define objective function and contraints

# objective 
def obj_expression(model):
    return sum(model.cap[i] * model.costs[i] for i in model.tech) + sum(model.ESS_d[t] * ESS_p_var_cost + model.curt[t] * curtailment_cost for t in model.t) 
model.OBJ = Objective(rule=obj_expression)

# supply/demand match constraint
def match_const(model, i):
    return model.solar[i]*model.cap['s_cap'] + model.wind[i]*model.cap['w_cap'] + model.ESS_d[i] - model.ESS_c[i] - model.curt[i] - model.demand[i] == 0   
model.match = Constraint(model.t, rule = match_const)

# ESS charge/discharge constraint
def ESS_charge_disc_const(model, i):
    return model.ESS_c[i] + model.ESS_d[i] <= model.cap['ESS_power_cap']   
model.ESS_charge_disc_rate = Constraint(model.t, rule = ESS_charge_disc_const)

# ESS max constraint
def ESS_max_const(model, i):
    return model.ESS_SOC[i] <= model.cap['ESS_energy_cap']   
model.ESS_max = Constraint(model.t, rule = ESS_max_const) 

# ESS min constraint
def ESS_min_const(model, i):
    return model.ESS_SOC[i] >= ESS_min_level * model.cap['ESS_energy_cap']   
model.ESS_min = Constraint(model.t, rule = ESS_min_const)      

# SOC constraint
def SOC_const(model, i):
    if i == model.t.first(): 
        return model.ESS_SOC[i] == model.ESS_SOC[model.t.last()] + (model.ESS_c[i] * ESS_eta_c) - (model.ESS_d[i]/ESS_eta_d) 
    return model.ESS_SOC[i] == model.ESS_SOC[i-1] + (model.ESS_c[i] * ESS_eta_c) - (model.ESS_d[i]/ESS_eta_d) 
model.SOC_const = Constraint(model.t, rule = SOC_const)


# create instance of the model (abstract only)
model = model.create_instance(data)

# look at model attributes
# model.t.pprint()

# solve the model
opt = SolverFactory('glpk')
# opt = SolverFactory('gurobi')
status = opt.solve(model) 

# write model outputs to a JSON file
model.solutions.store_to(status)
status.write(filename='DUBE_HWK3_OPT_OUTPUT.json', format='json')

# pyomo solve DUBE_HWK_3_OPT.py --solver=glpk
# pyomo solve solar_storage_model.py --solver=gurobi