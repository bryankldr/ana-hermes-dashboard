// services/pipeline.js — agent state → pipeline + matrix sync
// Extracted from main.js so behavior lives in one place.
export function createPipeline({ state, setMatrixActive }){
  const stageMap = { UNDERSTANDING:1, PLANNING:2, EXECUTING:4, ANALYZING:3, RESPONDING:5, WAITING_TOOL:4, LISTENING:0, IDLE:0, ERROR:-1 };
  return function setAgentState(agentState, coreLabel){
    state.agentStatus = agentState;
    if(coreLabel) coreLabel.textContent = agentState;
    const si = stageMap[agentState] ?? 0;
    document.querySelectorAll('.pipe-node').forEach((n,i)=> n.classList.toggle('active', i <= si && si>0));
    if(agentState==='EXECUTING') setMatrixActive('TOOL');
    else if(agentState==='ANALYZING') setMatrixActive('SRCH');
    else if(agentState==='RESPONDING') setMatrixActive('CODE');
    else setMatrixActive(null);
  };
}
