/* Existing serve distribution helpers; no UI. */
(()=>{
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));

  function poissonOver(mean,line){
    mean=Number(mean);line=Number(line);
    if(!Number.isFinite(mean)||mean<0||!Number.isFinite(line))return null;
    const threshold=Math.floor(line)+1;
    let term=Math.exp(-mean),cdf=term;
    for(let k=1;k<threshold;k++){term*=mean/k;cdf+=term}
    return clamp(1-cdf,0,1);
  }
  function modelPrice(p){return p>0.001?(1/p).toFixed(2):'—'}
  function lineValue(x){return Number.isFinite(Number(x))?Number(x):0.5}

window.TENIS_AI_SERVE_DISTRIBUTION={poissonOver,modelPrice,lineValue};
})();
