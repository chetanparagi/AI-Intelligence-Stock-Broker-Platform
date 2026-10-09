'use client';

import { useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Calculator, Plus, RotateCcw, Trash2 } from 'lucide-react';
import { inr } from '../lib/types';

type Mode='SIP'|'Step-up SIP'|'SWP'|'EMI'|'CAGR'|'Inflation'|'Retirement'|'Goal planning'|'FD/RD'|'XIRR';
type Flow={date:string;amount:number};
type Point={period:string;value:number;invested:number};
type Result={headline:number;headlineText:string;support:string;investedLabel:string;invested:number;deltaLabel:string;delta:number;schedule:Point[];showChart:boolean};
const modes:Mode[]=['SIP','Step-up SIP','SWP','EMI','CAGR','Inflation','Retirement','Goal planning','FD/RD','XIRR'];
const defaults={amount:10000,rate:12,years:15,step:10,principal:1000000,monthly:10000,current:1000000,target:5000000,inflation:6,targetCorpus:10000000,existing:500000};
const baseFlows:Flow[]=[{date:'2024-01-01',amount:-100000},{date:'2026-01-01',amount:125000}];
const calcXirr=(flows:Flow[]):number|null=>{const valid=flows.filter(f=>f.date&&Number.isFinite(Date.parse(f.date))&&Number.isFinite(f.amount));if(!valid.some(f=>f.amount<0)||!valid.some(f=>f.amount>0))return null;const start=Math.min(...valid.map(f=>new Date(f.date).getTime()));const npv=(r:number)=>valid.reduce((sum,f)=>sum+f.amount/Math.pow(1+r,(new Date(f.date).getTime()-start)/(365.25*86400000)),0);let rate=.1;for(let i=0;i<100;i++){const value=npv(rate);const derivative=valid.reduce((sum,f)=>{const y=(new Date(f.date).getTime()-start)/(365.25*86400000);return sum-y*f.amount/Math.pow(1+rate,y+1)},0);if(!Number.isFinite(derivative)||Math.abs(derivative)<1e-12)break;const next=rate-value/derivative;if(!Number.isFinite(next)||next<=-.9999||next>100)break;if(Math.abs(next-rate)<1e-9)return next;rate=next;}return Math.abs(npv(rate))<.01?rate:null;};

export default function Calculators(){
  const [mode,setMode]=useState<Mode>('SIP');const [v,setV]=useState(defaults);const [flows,setFlows]=useState(baseFlows);const [fdType,setFdType]=useState<'FD'|'RD'>('FD');
  const set=(key:keyof typeof defaults,value:number)=>setV(prev=>({...prev,[key]:Math.max(0,value)}));
  const years=Math.max(1,v.years),months=Math.max(1,Math.round(years*12)),monthlyRate=v.rate/1200;
  const result=useMemo<Result>(()=>{
    let invested=0,corpus=0,schedule:Point[]=[];
    if(mode==='SIP'||mode==='Step-up SIP'||mode==='Retirement'){
      let payment=v.amount;for(let m=1;m<=months;m++){corpus=(corpus+payment)*(1+monthlyRate);invested+=payment;if(m%12===0){schedule.push({period:`Year ${m/12}`,value:corpus,invested});if(mode==='Step-up SIP')payment*=1+v.step/100;}}
      return {headline:corpus,headlineText:'Estimated future corpus',support:`${inr(invested)} total contributions`,investedLabel:'Total contributions',invested,deltaLabel:'Estimated growth',delta:corpus-invested,schedule,showChart:true};
    }
    if(mode==='SWP'){
      corpus=v.principal;for(let m=1;m<=months;m++){const available=corpus*(1+monthlyRate),withdrawal=Math.min(v.monthly,available);corpus=available-withdrawal;invested+=withdrawal;if(m%12===0)schedule.push({period:`Year ${m/12}`,value:corpus,invested});}
      return {headline:corpus,headlineText:'Estimated ending balance',support:`${inr(invested)} withdrawals over ${years} years`,investedLabel:'Starting corpus',invested:v.principal,deltaLabel:'Withdrawals paid',delta:invested,schedule,showChart:true};
    }
    if(mode==='EMI'){
      const r=monthlyRate,n=months,emi=r===0?v.principal/n:v.principal*r*Math.pow(1+r,n)/(Math.pow(1+r,n)-1);let balance=v.principal;invested=emi*n;for(let m=1;m<=Math.min(n,120);m++){balance=Math.max(0,balance*(1+r)-emi);if(m%12===0)schedule.push({period:`Year ${m/12}`,value:balance,invested:emi*m});}
      return {headline:emi,headlineText:'Estimated monthly EMI',support:`${inr(invested)} total scheduled payments`,investedLabel:'Loan principal',invested:v.principal,deltaLabel:'Estimated interest',delta:Math.max(0,invested-v.principal),schedule,showChart:true};
    }
    if(mode==='CAGR'){
      const cagr=Math.pow(v.target/Math.max(v.current,1),1/years)-1;schedule=Array.from({length:Math.min(Math.floor(years),20)},(_,i)=>({period:`Year ${i+1}`,value:v.current*Math.pow(1+cagr,i+1),invested:v.current}));
      return {headline:cagr,headlineText:'Annualized CAGR',support:`From ${inr(v.current)} to ${inr(v.target)} in ${years} years`,investedLabel:'Starting value',invested:v.current,deltaLabel:'Total value change',delta:v.target-v.current,schedule,showChart:true};
    }
    if(mode==='Inflation'){
      corpus=v.amount*Math.pow(1+v.inflation/100,years);schedule=Array.from({length:Math.min(Math.floor(years),20)},(_,i)=>({period:`Year ${i+1}`,value:v.amount*Math.pow(1+v.inflation/100,i+1),invested:v.amount}));
      return {headline:corpus,headlineText:'Estimated future cost',support:`${v.amount?((corpus/v.amount-1)*100).toFixed(1):'0'}% increase at ${v.inflation}% annual inflation`,investedLabel:'Cost today',invested:v.amount,deltaLabel:'Inflation increase',delta:corpus-v.amount,schedule,showChart:true};
    }
    if(mode==='Goal planning'){
      const futureExisting=v.existing*Math.pow(1+monthlyRate,months),factor=monthlyRate===0?months:((Math.pow(1+monthlyRate,months)-1)/monthlyRate)*(1+monthlyRate);const required=Math.max(0,(v.targetCorpus-futureExisting)/factor);let balance=v.existing,contributed=v.existing;for(let m=1;m<=months;m++){balance=(balance+required)*(1+monthlyRate);contributed+=required;if(m%12===0)schedule.push({period:`Year ${m/12}`,value:balance,invested:contributed});}
      return {headline:required,headlineText:'Required monthly investment',support:`Projected goal corpus ${inr(balance)} against ${inr(v.targetCorpus)} target`,investedLabel:'Total contributions',invested:contributed,deltaLabel:'Estimated growth',delta:balance-contributed,schedule,showChart:true};
    }
    if(mode==='FD/RD'){
      if(fdType==='FD'){corpus=v.principal*Math.pow(1+v.rate/400,4*years);invested=v.principal;schedule=Array.from({length:Math.min(Math.floor(years),20)},(_,i)=>({period:`Year ${i+1}`,value:v.principal*Math.pow(1+v.rate/400,4*(i+1)),invested:v.principal}));}
      else {let monthly=v.monthly;for(let m=1;m<=months;m++){corpus=(corpus+monthly)*(1+monthlyRate);invested+=monthly;if(m%12===0)schedule.push({period:`Year ${m/12}`,value:corpus,invested});}}
      return {headline:corpus,headlineText:`Estimated ${fdType} maturity value`,support:`${inr(invested)} total deposit${fdType==='RD'?'s':''}`,investedLabel:'Total deposits',invested,deltaLabel:'Estimated interest',delta:corpus-invested,schedule,showChart:true};
    }
    const xirr=calcXirr(flows);const sorted=[...flows].sort((a,b)=>a.date.localeCompare(b.date));let cumulative=0;schedule=sorted.map(f=>{cumulative+=f.amount;return {period:f.date,value:cumulative,invested:0}});const outflows=flows.filter(f=>f.amount<0).reduce((a,f)=>a-f.amount,0),inflows=flows.filter(f=>f.amount>0).reduce((a,f)=>a+f.amount,0);
    return {headline:xirr??0,headlineText:xirr===null?'Add valid positive and negative dated cash flows':'Annualized XIRR',support:`${flows.length} dated cash flows included`,investedLabel:'Total invested',invested:outflows,deltaLabel:'Net cash flow gain',delta:inflows-outflows,schedule,showChart:false};
  },[mode,v,months,monthlyRate,years,fdType,flows]);
  const reset=()=>{setV(defaults);setFlows(baseFlows);setFdType('FD')};
  const fields: [keyof typeof defaults,string][] = mode==='EMI'?[['principal','Loan amount'],['rate','Annual interest rate'],['years','Loan tenure (years)']]
    :mode==='CAGR'?[['current','Starting value'],['target','Ending value'],['years','Holding period (years)']]
    :mode==='SWP'?[['principal','Starting corpus'],['monthly','Monthly withdrawal'],['rate','Expected annual return'],['years','Withdrawal period (years)']]
    :mode==='Inflation'?[['amount','Amount today'],['inflation','Annual inflation rate'],['years','Years ahead']]
    :mode==='Goal planning'?[['targetCorpus','Target corpus'],['existing','Current savings'],['rate','Expected annual return'],['years','Years to goal']]
    :mode==='FD/RD'?(fdType==='FD'?[['principal','Deposit amount'],['rate','Annual interest rate'],['years','Tenure (years)']]:[['monthly','Monthly RD deposit'],['rate','Annual interest rate'],['years','Tenure (years)']])
    :[['amount',mode==='Retirement'?'Monthly investment':'Monthly investment'],['rate','Expected annual return'],['years','Investment period (years)'],...(mode==='Step-up SIP'?[['step','Annual SIP increase'] as [keyof typeof defaults,string]]:[])];
  const labels:Record<Mode,string>={SIP:'SIP corpus estimate','Step-up SIP':'Step-up SIP estimate',SWP:'SWP sustainability estimate',EMI:'Loan EMI estimate',CAGR:'CAGR estimate',Inflation:'Inflation-adjusted cost',Retirement:'Retirement savings projection','Goal planning':'Goal planning', 'FD/RD':'Fixed and recurring deposit estimate',XIRR:'XIRR cash-flow return'};
  const percentInput=(key:string)=>['rate','step','inflation'].includes(key);
  return <div className="feature-page"><div className="feature-intro"><span className="feature-icon"><Calculator size={18}/></span><div><h2>Financial calculators</h2><p>Change assumptions to explore scenarios. Projections are estimates, not guaranteed returns.</p></div><button className="quiet-button" onClick={reset}><RotateCcw size={14}/> Reset</button></div>
    <div className="calc-tabs">{modes.map(m=><button key={m} className={mode===m?'active':''} onClick={()=>setMode(m)}>{m}</button>)}</div>
    <div className="calc-layout"><section className="feature-card calc-inputs"><div className="section-heading"><div><h3>{labels[mode]}</h3><p>Calculations update as you change an input</p></div></div>
      {mode==='FD/RD'&&<div className="calc-tabs compact-tabs">{(['FD','RD'] as const).map(t=><button key={t} className={fdType===t?'active':''} onClick={()=>setFdType(t)}>{t==='FD'?'Fixed deposit':'Recurring deposit'}</button>)}</div>}
      {mode==='XIRR'?<div className="cashflow-editor"><p>Add dated investment outflows as negative amounts and realizations as positive amounts.</p>{flows.map((f,i)=><div className="cashflow-row" key={i}><input type="date" value={f.date} onChange={e=>setFlows(fs=>fs.map((x,j)=>j===i?{...x,date:e.target.value}:x))}/><input type="number" value={f.amount} onChange={e=>setFlows(fs=>fs.map((x,j)=>j===i?{...x,amount:Number(e.target.value)}:x))} aria-label={`Cash flow amount ${i+1}`}/><button aria-label="Remove cash flow" onClick={()=>setFlows(fs=>fs.filter((_,j)=>j!==i))}><Trash2 size={14}/></button></div>)}<button className="quiet-button" onClick={()=>setFlows(fs=>[...fs,{date:new Date().toISOString().slice(0,10),amount:0}])}><Plus size={13}/> Add cash flow</button></div>:fields.map(([key,label])=><label className="calc-field" key={key}><span>{label}</span><div><input type="number" min="0" max={key==='years'?50:100000000} value={v[key]} onChange={e=>set(key,Number(e.target.value))}/><span>{key==='years'?'years':percentInput(key)?'%':'₹'}</span></div><input className="range-input" type="range" min="0" max={key==='years'?50:percentInput(key)?30:10000000} step={key==='years'?1:percentInput(key)?0.5:1000} value={Math.min(v[key],key==='years'?50:percentInput(key)?30:10000000)} onChange={e=>set(key,Number(e.target.value))}/></label>)}
      <div className="formula-box"><strong>Calculation method</strong><p>{mode==='SIP'||mode==='Step-up SIP'||mode==='Retirement'?'Monthly contributions compound at the entered annual rate. Step-up SIP increases contributions once per year.':mode==='SWP'?'Each month the remaining corpus earns the entered return, then the withdrawal is deducted.':mode==='EMI'?'Reducing-balance EMI from principal, monthly rate and number of payments.':mode==='CAGR'?'Annualized growth rate connecting start and end values.':mode==='Inflation'?'Future nominal cost is amount today × (1 + inflation rate) ^ years.':mode==='Goal planning'?'Required monthly investment solves for the entered target after growth on current savings.':mode==='FD/RD'?'FD uses quarterly compounding; RD compounds monthly deposits at the entered annual rate.':mode==='XIRR'?'Newton iteration solves the annual rate that sets dated cash-flow NPV to zero using actual day counts.':'Projection assumes the monthly investment continues until the selected date.'}</p></div>
    </section><section className="feature-card calc-results"><div className="result-hero"><span>{result.headlineText.toUpperCase()}</span><strong>{mode==='CAGR'||mode==='XIRR'?`${(result.headline*100).toFixed(2)}%`:inr(result.headline)}</strong><small>{result.support}</small></div>{result.showChart&&<div className="calc-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={result.schedule.filter((_,i)=>i%Math.max(1,Math.ceil(result.schedule.length/10))===0)} margin={{top:8,right:6,left:0,bottom:0}}><CartesianGrid vertical={false} stroke="#edf0ed"/><XAxis dataKey="period" tick={{fontSize:9,fill:'#89938b'}} axisLine={false} tickLine={false}/><YAxis tickFormatter={n=>`${Math.round(n/100000)}L`} tick={{fontSize:9,fill:'#89938b'}} axisLine={false} tickLine={false}/><Tooltip formatter={(n:any)=>inr(n)} contentStyle={{border:'1px solid #e8ece8',borderRadius:8,fontSize:11}}/><Bar dataKey="value" name={mode==='EMI'?'Remaining loan balance':'Estimated value'} fill="#5a8b70" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer></div>}{mode==='XIRR'&&<div className="xirr-explainer">XIRR uses the exact dates and signed cash flows above. Check that all dates and transaction amounts are correct; multiple sign changes can produce ambiguous results.</div>}<div className="calc-output-row"><div><span>{result.investedLabel}</span><strong>{inr(result.invested)}</strong></div><div><span>{result.deltaLabel}</span><strong>{inr(result.delta)}</strong></div></div><p className="calc-caveat">Assumptions are constant and exclude taxes, fees, product rules and market variability unless entered. These estimates are educational, not investment advice.</p></section></div></div>;
}
