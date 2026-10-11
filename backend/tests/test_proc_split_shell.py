"""Exercise real shell range handlers with independent material/mechanical months."""
import json
import subprocess

from tests.acc_plugin import acc
from tests.shell_src import act_entry, func_body


def run_js(code):
    result = subprocess.run(["node"], input=code, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


@acc()
def test_independent_cutoffs_preview_invalidation_and_project_switch():
    options = func_body("impOptions")
    handlers = act_entry("impCutEdit") + "\n" + act_entry("impMechCutEdit")
    pick = act_entry("impPjPick")
    result = run_js("""
const ACT={}, IMP={cutoff:'2025-11',mechanicalCutoff:'2026-09',preview:{},problems:[],
  hasCut:true,hasMechCut:true,cutoffs:{A:'2025-11',B:'2025-10'},
  mechanicalCutoffs:{A:'2026-09',B:'2026-08'},pjDisp:{},wrap:'A'};
const document={querySelector:()=>null};
const bjMonth=()=> '2026-10', pjClose=()=>{}, render=()=>{}, toast=()=>{}, esc=x=>x;
""" + options + "\n" + handlers + "\n" + pick + """
const a=impOptions();
ACT.impMechCutEdit({value:'2026-08'});
const invalid=IMP.preview===null && IMP.cutoff==='2025-11';
IMP.preview={}; ACT.impCutEdit({value:'2025-10'});
const invalidMaterial=IMP.preview===null && IMP.mechanicalCutoff==='2026-08';
ACT.impPjPick({dataset:{pj:'A'}}); const b=impOptions();
ACT.impPjPick({dataset:{pj:'B'}}); const c=impOptions();
console.log(JSON.stringify({a,b,c,invalid,invalidMaterial}));
""")
    assert result["a"]["material_cutoff_ym"] == "2025-11"
    assert result["a"]["mechanical_cutoff_ym"] == "2026-09"
    assert result["invalid"] and result["invalidMaterial"]
    assert result["b"]["mechanical_cutoff_ym"] == "2026-09"
    assert result["c"]["material_cutoff_ym"] == "2025-10"
    assert result["c"]["mechanical_cutoff_ym"] == "2026-08"


@acc()
def test_mechanical_history_month_reaches_real_save_action():
    body = act_entry("procMechSave").strip().removeprefix("procMechSave:")
    result = run_js("""
let procMechWrites=Promise.resolve();
const calls=[], MECH_SECTIONS={A:{'2025-01':'history'}};
const document={activeElement:null};
const API={m06MechSave:async p=>{calls.push(p);return {ok:true}}};
const reloadMech=async()=>{},reloadProc=async()=>{},reloadM07=async()=>{},render=()=>{},toast=()=>{},esc=x=>x;
const save=""" + body + """;
const t={dataset:{wh:'A',ym:'2025-01',i:'0'},value:'123.45',defaultValue:'1200',blur:()=>{}};
save(t).then(()=>console.log(JSON.stringify(calls)));
""")
    assert result == [{"warehouse": "A", "ym": "2025-01", "values": {"mech_0": "123.45"}}]
