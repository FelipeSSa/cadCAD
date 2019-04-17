from datetime import timedelta

from cadCAD.configuration import append_configs
from cadCAD.configuration.utils import ep_time_step, config_sim
# from cadCAD.configuration.utils.policyAggregation import dict_op, dict_elemwise_sum
from cadCAD.configuration.utils.udo import udcBroker, udoPipe, UDO
import pandas as pd
from cadCAD.utils import SilentDF, val_switch

ds = SilentDF(pd.read_csv('/Users/jjodesty/Projects/DiffyQ-SimCAD/simulations/output.csv'))


class MyClass(object):
    def __init__(self, x, ds=None):
        self.x = x
        self.ds = ds # for setting ds initially or querying

    def update(self):
        self.x += 1
        return self

    def read(self, ds_uri):
        self.ds = SilentDF(pd.read_csv(ds_uri))
        return self

    def write(self, ds_uri):
        pd.to_csv(ds_uri)

    def getMemID(self):
        return str(hex(id(self)))

    pass


# can be accessed after an update within the same substep and timestep

hydra_state_view = UDO(MyClass(0, ds))
udc_view_A = UDO(MyClass(0, ds))
udc_view_B = UDO(MyClass(0, ds))

print(udc_view_A)

# g: Dict[str, List[int]] = {'MyClassB'}

state_dict = {
    'a': 0, 'b': 0, 'j': 0,
    'k': (0, 0), 'q': (0, 0),
    'hydra_state': hydra_state_view,
    'policies': {'hydra_A': udc_view_A, 'hydra_B': udc_view_B},
    'timestamp': '2019-01-01 00:00:00',
    'c': {"ds1": None, "ds2": None, "ds3": None, "timestep": None}
}

def p1(_g, step, sL, s):
    s['policies']['hydra_A'].update()
    return {'hydra_A': udoPipe(s['policies']['hydra_A'])}

def p2(_g, step, sL, s):
    s['policies']['hydra_B'].update()
    # df = s['policies']['hydra_B'].ds
    return {'hydra_B': udoPipe(s['policies']['hydra_B'])}

# ToDo: SilentDF(df) wont work
def C(_g, step, sL, s, _input):
    y = 'c'
    ds = _input['hydra_B'].ds
    df = ds[(ds['run'] == s['run']) & (ds['substep'] == s['substep']) & (ds['timestep'] == s['timestep'])].drop(columns=['run', 'substep'])
    def pop_if_not_empty(l):
        if len(l) == 0:
            return None
        else:
            return l.pop()

    x = {k: pop_if_not_empty(list(v.values())) for k, v in df.to_dict().items()} # reomve idx
    return (y, x)

def policies(_g, step, sL, s, _input):
    y = 'policies'
    x = _input
    return (y, x)

timestep_duration = timedelta(minutes=1) # In this example, a timestep has a duration of 1 minute.
ts_format = '%Y-%m-%d %H:%M:%S'
def time_model(_g, step, sL, s, _input):
    y = 'timestamp'
    x = ep_time_step(s, dt_str=s['timestamp'], fromat_str=ts_format, _timedelta=timestep_duration)
    return (y, x)


def HydraMembers(_g, step, sL, s, _input):
    y = 'hydra_state'
    s['hydra_state'].update()
    x = udoPipe(s['hydra_state'])
    return (y, x)

def repr(_g, step, sL, s, _input):
    y = 'z'
    x = s['hydra_members'].__repr__()
    return (y, x)

def incriment(y, incr_val):
    return lambda _g, step, sL, s, _input: (y, s[y] + incr_val)

def A(_g, step, sL, s, _input):
    y = 'a'
    x = s['a'] + 1
    return (y, x)

def hydra_state_tracker(y):
    return lambda _g, step, sL, s, _input: (y, s['hydra_state'].x)


def hydra_policy_tracker(y):
    return lambda _g, step, sL, s, _input: (y, tuple(val_switch(v) for k, v in s['policies'].items()))


# needs M1&2 need behaviors
partial_state_update_blocks = {
    'PSUB1': {
        'policies': {
            "b1": p1,
            "b2": p2
        },
        'states': {
            'a': A,
            'b': hydra_state_tracker('b'),
            'c': C,
            'j': hydra_state_tracker('j'),
            'k': hydra_policy_tracker('k'),
            'q': hydra_policy_tracker('q'),
            'hydra_state': HydraMembers,
            'timestamp': time_model,
            'policies': policies
        }
    },
    'PSUB2': {
        'policies': {
            "b1": p1,
            "b2": p2
        },
        'states': {
            'a': A,
            'b': hydra_state_tracker('b'),
            'c': C,
            'j': hydra_state_tracker('j'),
            'k': hydra_policy_tracker('k'),
            'q': hydra_policy_tracker('q'),
            'hydra_state': HydraMembers,
            'policies': policies
        }
    },
    'PSUB3': {
        'policies': {
            "b1": p1,
            "b2": p2
        },
        'states': {
            'a': A,
            'b': hydra_state_tracker('b'),
            'c': C,
            'j': hydra_state_tracker('j'),
            'k': hydra_policy_tracker('k'),
            'q': hydra_policy_tracker('q'),
            'hydra_state': HydraMembers,
            'policies': policies
        }
    }
}

sim_config = config_sim({
    "N": 2,
    "T": range(4)
})
z = {'z': 1}

def addZ(d, z):
    d.update(z)
    return d

append_configs(
    sim_config,
    state_dict,
    {}, {}, {},
    partial_state_update_blocks,
    policy_ops=[lambda a, b: {**a, **b}]
)
