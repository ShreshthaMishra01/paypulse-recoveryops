import { useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowRight, BarChart3, BrainCircuit, Check,
  ChevronRight, CircleDollarSign, Clock3, Database, FileCheck2, FlaskConical,
  Gauge, IndianRupee, Info, LayoutDashboard, LockKeyhole, Play, RefreshCw,
  Route, Search, ShieldCheck, Sparkles, TerminalSquare, TrendingUp, Zap,
  ExternalLink, BadgeCheck,
} from 'lucide-react'

const money = value => new Intl.NumberFormat('en-IN', {
  style: 'currency', currency: 'INR', maximumFractionDigits: 0,
}).format(value || 0)

const pct = value => `${Number(value || 0).toFixed(1)}%`

function Sidebar() {
  const items = [
    [LayoutDashboard, 'Command center', 'overview'],
    [AlertTriangle, 'Incident', 'incident'],
    [BrainCircuit, 'Causal policy', 'experiment'],
    [Route, 'Recovery queue', 'queue'],
    [FileCheck2, 'Proof ledger', 'ledger'],
  ]
  return <aside className="sidebar">
    <div className="brand">
      <div className="brandMark"><Activity size={20}/></div>
      <div><strong>PayPulse</strong><span>RECOVERY OPS</span></div>
    </div>
    <nav>{items.map(([Icon, label, id], index) =>
      <a className={index === 0 ? 'active' : ''} href={`#${id}`} key={id}>
        <Icon size={17}/><span>{label}</span>{index === 1 && <b>1</b>}
      </a>
    )}</nav>
    <div className="sidebarBottom">
      <div className="safetyBadge"><ShieldCheck size={16}/><div><b>Shadow mode</b><small>No live money actions</small></div></div>
      <div className="merchant"><div className="avatar">AC</div><div><b>Acme Commerce</b><small>Test merchant</small></div></div>
    </div>
  </aside>
}

function KpiCard({icon: Icon, label, value, note, accent}) {
  return <div className={`kpi ${accent || ''}`}>
    <div className="kpiTop"><span>{label}</span><Icon size={17}/></div>
    <div className="kpiValue">{value}</div>
    <div className="kpiNote">{note}</div>
  </div>
}

function Timeline({points = []}) {
  const series = points.slice(-18)
  const width = 760, height = 178, pad = 18
  const max = Math.max(35, ...series.map(p => p.failure_rate))
  const coords = series.map((p, i) => {
    const x = pad + (i * (width - pad * 2)) / Math.max(1, series.length - 1)
    const y = height - pad - (p.failure_rate / max) * (height - pad * 2)
    return [x, y]
  })
  const line = coords.map((p, i) => `${i ? 'L' : 'M'} ${p[0]} ${p[1]}`).join(' ')
  const area = coords.length ? `${line} L ${coords.at(-1)[0]} ${height-pad} L ${coords[0][0]} ${height-pad} Z` : ''
  return <div className="chartWrap">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Payment failure rate timeline">
      {[0.25, .5, .75].map(t => <line key={t} x1={pad} x2={width-pad} y1={height*t} y2={height*t} className="gridLine" />)}
      <path d={area} className="area" />
      <path d={line} className="line" />
      {coords.map((p, i) => i === coords.length - 1 ? <circle key={i} cx={p[0]} cy={p[1]} r="5" className="point"/> : null)}
    </svg>
    <div className="chartLabels"><span>18h ago</span><span>12h</span><span>6h</span><span>Now</span></div>
  </div>
}

function Experiment({experiment}) {
  if (!experiment) return null
  const policy = experiment.predicted_recovered_current_batch
  const baseline = experiment.predicted_blind_retry_current_batch
  const max = Math.max(policy, baseline, 1)
  const lift = experiment.predicted_incremental_current_batch
  return <section className="panel experiment" id="experiment">
    <div className="panelHead">
      <div><span className="eyebrow">OFFLINE POLICY EVALUATION</span><h2>Recovery policy vs blind retry</h2></div>
      <span className="method"><FlaskConical size={14}/>{experiment.evaluation_method}</span>
    </div>
    <div className="experimentHero">
      <div><small>MODEL-ESTIMATED INCREMENTAL RECOVERY</small><strong>{money(lift)}</strong><span>on {experiment.current_batch_size} affected failures</span></div>
      <div className="confidence"><span>95% holdout interval / failure</span><b>{money(experiment.ips_95_ci_per_failure?.[0])} to {money(experiment.ips_95_ci_per_failure?.[1])}</b></div>
    </div>
    <div className="barCompare">
      <div className="barRow"><label><b>PayPulse policy</b><span>{money(policy)}</span></label><div className="barTrack"><div className="bar fillGreen" style={{width: `${policy/max*100}%`}}/></div></div>
      <div className="barRow"><label><b>Blind retry</b><span>{money(baseline)}</span></label><div className="barTrack"><div className="bar fillGray" style={{width: `${baseline/max*100}%`}}/></div></div>
    </div>
    <div className="experimentStats">
      <div><span>Action model AUC</span><b>{experiment.mean_action_auc}</b></div>
      <div><span>Holdout records</span><b>{experiment.holdout_size}</b></div>
      <div><span>IPS value / failure</span><b>{money(experiment.ips_policy_value_per_failure)}</b></div>
    </div>
    <p className="disclaimer"><Info size={14}/>{experiment.disclaimer}</p>
  </section>
}

function ActionBreakdown({items = []}) {
  const icons = {alternate_method: Route, retry_30m: Clock3, payment_link: Zap, no_action: ShieldCheck}
  return <section className="panel actionsPanel">
    <div className="panelHead"><div><span className="eyebrow">BOUNDED DECISIONS</span><h2>Recommended playbook</h2></div></div>
    <div className="actionList">{items.map(item => {
      const Icon = icons[item.action] || Zap
      return <div className="actionItem" key={item.action}>
        <div className={`actionIcon ${item.action}`}><Icon size={17}/></div>
        <div className="actionText"><b>{item.label}</b><span>{item.count} payments</span></div>
        <strong>{money(item.expected_incremental_value)}</strong>
      </div>
    })}</div>
    <div className="guardrail"><LockKeyhole size={16}/><span><b>Policy guardrails active</b> Contact budget, retry ceiling and high-value approval enforced.</span></div>
  </section>
}

function Incident({incident, explanation, onExplain, explaining}) {
  if (!incident) return null
  return <section className="panel incident" id="incident">
    <div className="incidentTop">
      <div className="alertIcon"><AlertTriangle size={20}/></div>
      <div className="incidentTitle"><div><span className="liveDot"/>LIVE INCIDENT · {incident.incident_id}</div><h1>{incident.title}</h1></div>
      <div className="confidencePill"><span>RCA confidence</span><b>{pct(incident.confidence)}</b></div>
    </div>
    <div className="incidentGrid">
      <div className="incidentChart">
        <div className="chartHead"><span>FAILURE RATE · LAST 18 HOURS</span><div><b>{pct(incident.current_failure_rate)}</b><small>from {pct(incident.baseline_failure_rate)}</small></div></div>
        <Timeline points={incident.timeline}/>
      </div>
      <div className="rootCause">
        <span className="eyebrow">LIKELY ROOT CAUSE</span>
        <h3>{incident.root_cause}</h3>
        <p>The error mix shifted toward <code>{incident.likely_error}</code> inside a sharply degraded payment cohort.</p>
        <div className="filterTags">{Object.entries(incident.affected_filters).map(([k,v]) => <span key={k}>{k}: <b>{v}</b></span>)}</div>
        <div className="impactLine"><CircleDollarSign size={18}/><div><span>Revenue at risk</span><b>{money(incident.revenue_at_risk)}</b></div></div>
        <button className="ghostBtn" onClick={onExplain} disabled={explaining}><Sparkles size={15}/>{explaining ? 'Analyzing evidence…' : 'Explain with Gemini'}</button>
      </div>
    </div>
    {explanation && <div className="aiExplanation"><Sparkles size={17}/><div><b>Evidence-grounded briefing <span>{explanation.provider}</span></b><p>{explanation.text}</p></div></div>}
    <div className="evidenceStrip">
      {incident.evidence?.slice(0,4).map((e, i) => <div key={i}>
        <span>{e.label}</span><b>{pct(e.current_rate)}</b><small>+{e.delta_pp}pp · {e.transactions} txns</small>
      </div>)}
    </div>
  </section>
}

function Queue({recommendations = [], onExecute, onVerify, busy}) {
  return <section className="panel queue" id="queue">
    <div className="panelHead">
      <div><span className="eyebrow">EXPECTED-VALUE RANKING</span><h2>Recovery queue</h2></div>
      <span className="method"><ShieldCheck size={14}/>Consent aware</span>
    </div>
    <div className="tableScroll"><table>
      <thead><tr><th>PAYMENT</th><th>FAILURE</th><th>RECOMMENDED ACTION</th><th>UPLIFT</th><th>EXPECTED VALUE</th><th>MODE</th><th></th></tr></thead>
      <tbody>{recommendations.slice(0,10).map(rec => <tr key={rec.payment_id}>
        <td><b>{rec.payment_id.replace('pay_demo_', '#')}</b><span>{money(rec.amount)} · {rec.method}</span></td>
        <td><code>{rec.error_code.replaceAll('_',' ')}</code></td>
        <td className="decision"><b>{rec.action_label}</b><span>{rec.reason}</span></td>
        <td><b className="positive">+{rec.incremental_uplift_pp}pp</b><span>{pct(rec.confidence)} conf.</span></td>
        <td><b>{money(rec.expected_incremental_value)}</b></td>
        <td><span className={`mode ${rec.execution_mode}`}>{rec.execution_mode.replace('_mock','').replaceAll('_',' ')}</span></td>
        <td><div className="tableActions">
          {rec.recommended_action !== 'no_action' && rec.status === 'recommended' &&
            <button title="Execute bounded test action" className="execute" disabled={busy === rec.payment_id} onClick={() => onExecute(rec.payment_id)}>{busy === rec.payment_id ? <RefreshCw size={14} className="spin"/> : <Play size={14}/>}</button>}
          {rec.status === 'awaiting_payment' && <>
            <a title="Open Razorpay test checkout" className="execute" href={rec.execution?.checkout_url} target="_blank" rel="noreferrer"><ExternalLink size={14}/></a>
            <button title="Verify payment status" className="execute" disabled={busy === rec.payment_id} onClick={() => onVerify(rec.payment_id)}>{busy === rec.payment_id ? <RefreshCw size={14} className="spin"/> : <BadgeCheck size={14}/>}</button>
          </>}
          {['executed','scheduled','recovered'].includes(rec.status) && <Check size={17} className="positive"/>}
        </div></td>
      </tr>)}</tbody>
    </table></div>
  </section>
}

function Ledger({audit = []}) {
  return <section className="panel ledger" id="ledger">
    <div className="panelHead"><div><span className="eyebrow">IMMUTABLE DECISION TRAIL</span><h2>Recovery proof ledger</h2></div><span className="hash">SHA-256 chained · demo</span></div>
    <div className="ledgerList">{audit.map((entry, i) => <div className="ledgerEntry" key={entry.event_id}>
      <div className="ledgerNode"><Check size={13}/></div>
      <div><span>{entry.type}</span><b>{entry.message}</b><small>{entry.actor} · evidence {entry.evidence_ref}</small></div>
      <time>{new Date(entry.time).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</time>
    </div>)}</div>
  </section>
}

function ModelCard({card, integration}) {
  return <section className="panel modelPanel">
    <div className="panelHead"><div><span className="eyebrow">MODEL & INTEGRATION CARD</span><h2>Transparent by design</h2></div></div>
    <div className="modelGrid">
      <div><Database size={17}/><span>Training</span><b>{card.train_rows?.toLocaleString()} randomized records</b></div>
      <div><BrainCircuit size={17}/><span>Outcome model</span><b>{card.outcome_models}</b></div>
      <div><Gauge size={17}/><span>Temporal holdout</span><b>{card.holdout_rows?.toLocaleString()} records</b></div>
      <div><TerminalSquare size={17}/><span>Razorpay adapter</span><b>{integration?.mode || 'mock'} mode</b></div>
    </div>
    <div className="limits"><b>Known limitations</b>{card.known_limitations?.map(x => <span key={x}><ChevronRight size={13}/>{x}</span>)}</div>
  </section>
}

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [resetting, setResetting] = useState(false)
  const [busy, setBusy] = useState('')
  const [explanation, setExplanation] = useState(null)
  const [explaining, setExplaining] = useState(false)

  const load = async () => {
    try {
      const res = await fetch('/api/dashboard')
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      setData(await res.json()); setError('')
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const reset = async () => {
    setResetting(true); setExplanation(null)
    try {
      const res = await fetch('/api/demo/reset', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({seed: 42})})
      setData(await res.json())
    } finally { setResetting(false) }
  }
  const explain = async () => {
    setExplaining(true)
    try { const res = await fetch(`/api/incidents/${data.incident.incident_id}/explanation`); setExplanation(await res.json()) }
    finally { setExplaining(false) }
  }
  const execute = async paymentId => {
    setBusy(paymentId)
    const popup = window.open('', '_blank')
    try {
      const res = await fetch(`/api/actions/${paymentId}/execute`, {method:'POST'})
      const payload = await res.json()
      if (!res.ok) throw new Error(payload.detail || 'Recovery action failed')
      if (payload.checkout_url && popup) popup.location.href = payload.checkout_url
      else if (popup) popup.close()
      await load()
    } catch (e) {
      if (popup) popup.close()
      alert(e.message)
    } finally { setBusy('') }
  }
  const verify = async paymentId => {
    setBusy(paymentId)
    try {
      const res = await fetch(`/api/actions/${paymentId}/verify`, {method:'POST'})
      const payload = await res.json()
      if (!res.ok) throw new Error(payload.detail || 'Status verification failed')
      if (payload.paid === false) alert(`Razorpay status: ${payload.status}. Complete the test checkout first.`)
      await load()
    } catch (e) { alert(e.message) } finally { setBusy('') }
  }

  if (loading) return <div className="center"><div className="pulseLogo"><Activity/></div><p>Building the recovery picture…</p></div>
  if (error || !data) return <div className="center errorState"><AlertTriangle/><h2>PayPulse API is unavailable</h2><p>{error}</p><button onClick={load}>Retry</button></div>

  const s = data.summary
  return <div className="appShell">
    <Sidebar />
    <main>
      <header>
        <div><span className="breadcrumb">OPERATIONS <ChevronRight size={13}/> COMMAND CENTER</span><h1>Revenue recovery, with proof.</h1><p>Detect incidents, choose incremental actions, and account for every recovered rupee.</p></div>
        <div className="headerActions"><span className="stream"><i/>Event stream live</span><button onClick={reset} disabled={resetting}><RefreshCw size={15} className={resetting?'spin':''}/>{resetting?'Replaying…':'Replay incident'}</button></div>
      </header>

      <div className="notice"><FlaskConical size={16}/><b>Synthetic evaluation environment.</b><span>All revenue outcomes are model estimates—not production claims.</span></div>

      <section className="kpiGrid" id="overview">
        <KpiCard icon={Search} label="Payments analyzed" value={s.payments_analyzed.toLocaleString()} note="48-hour event window" />
        <KpiCard icon={AlertTriangle} label="Revenue at risk" value={money(s.revenue_at_risk)} note="Active incident cohort" accent="risk" />
        <KpiCard icon={TrendingUp} label="Incremental recovery" value={money(s.predicted_incremental_recovery)} note="vs blind retry · estimated" accent="gain" />
        <KpiCard icon={ShieldCheck} label="Bounded actions" value={s.auto_safe_actions + s.approval_actions} note={`${s.approval_actions} need approval`} />
      </section>

      <Incident incident={data.incident} explanation={explanation} onExplain={explain} explaining={explaining}/>
      <div className="twoCol"><Experiment experiment={data.experiment}/><ActionBreakdown items={data.action_breakdown}/></div>
      <Queue recommendations={data.recommendations} onExecute={execute} onVerify={verify} busy={busy}/>
      <div className="twoCol bottom"><Ledger audit={data.audit}/><ModelCard card={data.model_card} integration={data.integration}/></div>
      <footer><span>PayPulse RecoveryOps · Buildathon MVP</span><span><LockKeyhole size={13}/>LLMs cannot execute money actions</span></footer>
    </main>
  </div>
}
