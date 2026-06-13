import { useEffect, useMemo, useState } from "react";
import {
  ActivityIcon as Activity, ArrowClockwiseIcon as ArrowClockwise, ChartLineUpIcon as ChartLineUp,
  CheckCircleIcon as CheckCircle, ClockCounterClockwiseIcon as ClockCounterClockwise,
  DatabaseIcon as Database, FileTextIcon as FileText, HorseIcon as Horse, InfoIcon as Info,
  ListChecksIcon as ListChecks, MagnifyingGlassIcon as MagnifyingGlass, PaperPlaneTiltIcon as PaperPlaneTilt,
  ShieldCheckIcon as ShieldCheck, ShieldWarningIcon as ShieldWarning, SparkleIcon as Sparkle,
  ThumbsDownIcon as ThumbsDown, ThumbsUpIcon as ThumbsUp, TrashIcon as Trash, WarningIcon as Warning
} from "@phosphor-icons/react";

const samples = [
  ["风险样例", "恭喜您获得幸运大奖，请立即点击链接领取奖金并填写银行卡信息。"],
  ["正常通知", "通知：明天下午三点在会议室召开项目例会，请准时参加。"],
  ["生活信息", "您的快递已放在小区丰巢柜，请凭取件码及时签收。"],
];
const initialHistory = [
  { time: "09:42", text: "项目例会将于下午三点召开，请准时参加。", label: "正常短信", score: 4, category: "正常通知" },
  { time: "09:31", text: "恭喜中奖，请点击链接领取现金大奖。", label: "风险短信", score: 99, category: "诈骗诱导" },
  { time: "09:18", text: "您的快递已到达，请及时签收。", label: "正常短信", score: 2, category: "正常通知" },
];
const nav = [["scan", MagnifyingGlass, "智能检测"], ["batch", ListChecks, "批量扫描"], ["history", ClockCounterClockwise, "检测记录"], ["model", ChartLineUp, "模型表现"]];

function Brand() {
  return <div className="brand"><div className="brand-mark"><Horse weight="fill" /></div><div><strong>白马卫士</strong><span>白马伴您身旁，为爱守护</span></div></div>;
}
function ScoreRing({ score, risky }) {
  return <div className={`score-ring ${risky ? "danger" : "safe"}`} style={{ "--score": `${score * 3.6}deg` }}><div><strong>{score}%</strong><span>风险概率</span></div></div>;
}

export function App() {
  const [view, setView] = useState("scan");
  const [text, setText] = useState(samples[0][1]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);
  const [history, setHistory] = useState(() => JSON.parse(localStorage.getItem("baima-history") || "null") || initialHistory);
  const [feedback, setFeedback] = useState("");
  const refreshHealth = () => fetch("/api/health").then(r => r.json()).then(setHealth).catch(() => setHealth(null));
  useEffect(() => { refreshHealth(); }, []);
  useEffect(() => { localStorage.setItem("baima-history", JSON.stringify(history)); }, [history]);
  const metrics = useMemo(() => {
    const risky = history.filter(x => x.label === "风险短信").length;
    return [["今日检测", history.length, Activity, "cyan"], ["风险拦截", risky, ShieldWarning, "red"], ["正常放行", history.length - risky, ShieldCheck, "green"], ["已学习反馈", health?.feedback_count || 0, Info, "amber"]];
  }, [history, health]);

  async function analyze(content = text) {
    if (!content.trim()) { setError("请输入需要检测的短信内容"); return; }
    setText(content); setLoading(true); setError(""); setFeedback("");
    try {
      const response = await fetch("/api/predict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: content }) });
      if (!response.ok) throw new Error("检测服务暂时不可用");
      const data = await response.json(); setResult(data);
      setHistory(items => [{ time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }), text: content, label: data.label, score: Math.round(data.risk_probability * 100), category: data.category }, ...items].slice(0, 20));
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }

  async function submitFeedback(isCorrect) {
    if (!result) return;
    setFeedback("提交中");
    try {
      const response = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, predicted_class: result.class_id, is_correct: isCorrect }),
      });
      if (!response.ok) throw new Error("反馈保存失败");
      const saved = await response.json();
      setFeedback(isCorrect ? "准确反馈已保存" : "误报已纠正并学习");
      await refreshHealth();
      if (!isCorrect) {
        const corrected = await fetch("/api/predict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
        setResult(await corrected.json());
      }
      return saved;
    } catch (e) {
      setFeedback(e.message);
    }
  }

  return <div className="app-shell">
    <aside><Brand /><nav>{nav.map(([id, Icon, label]) => <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)}><Icon size={20} />{label}</button>)}</nav><div className="aside-card"><div className="online"><i />检测服务在线</div><strong>Hybrid Guard v1.2</strong><span>模型、策略与反馈学习</span></div><div className="aside-foot"><ShieldCheck size={18} />本地安全运行</div></aside>
    <main><header><div><span className="eyebrow">MESSAGE SECURITY CENTER</span><h1>{nav.find(x => x[0] === view)?.[2]}</h1></div><div className="header-status"><i />防护运行中 <span>{new Date().toLocaleDateString("zh-CN")}</span></div></header>
      {view === "scan" && <><section className="metrics">{metrics.map(([label, value, Icon, color]) => <article key={label}><div className={`metric-icon ${color}`}><Icon size={22} /></div><div><span>{label}</span><strong>{value}</strong></div><small>实时更新</small></article>)}</section>
        <section className="scan-grid"><article className="panel input-panel"><div className="panel-title"><div><span className="step">01</span><h2>输入待检测信息</h2></div><button className="ghost" onClick={() => { setText(""); setResult(null); }}><Trash />清空</button></div><textarea value={text} onChange={e => setText(e.target.value)} placeholder="粘贴短信、聊天消息或通知内容..." maxLength={1000} /><div className="input-meta"><span>{text.length} / 1000 字</span><span>内容仅用于本次判断</span></div><div className="sample-row">{samples.map(([label, content]) => <button key={label} onClick={() => analyze(content)}><Sparkle />{label}</button>)}</div>{error && <div className="error"><Warning />{error}</div>}<button className="primary" disabled={loading} onClick={() => analyze()}>{loading ? <ArrowClockwise className="spin" /> : <PaperPlaneTilt weight="fill" />}{loading ? "模型分析中..." : "立即智能检测"}</button></article>
          <article className={`panel result-panel ${result ? (result.class_id ? "is-danger" : "is-safe") : ""}`}><div className="panel-title"><div><span className="step">02</span><h2>智能判断结果</h2></div>{result && <span className="model-tag">模型 + 策略 + 反馈学习</span>}</div>{!result ? <div className="empty-result"><ShieldCheck size={64} /><h3>等待检测</h3><p>输入信息后，白马卫士会给出风险概率、判断依据和处置建议。</p></div> : <div className="result-content"><div className="result-hero"><ScoreRing score={Math.round(result.risk_probability * 100)} risky={result.class_id} /><div><span className="result-kicker">{result.risk_level}</span><h3>{result.label}</h3><p>{result.suggested_action}</p></div></div><div className="result-tags"><span>{result.category}</span><span>置信度 {Math.round(result.confidence * 100)}%</span><span>阈值 {Math.round(result.risk_threshold * 100)}%</span>{result.feedback_learned && <span>已应用反馈学习</span>}</div><div className="evidence"><h4><FileText />判断依据</h4>{result.evidence.map(item => <p key={item}><CheckCircle weight="fill" />{item}</p>)}</div><div className="feedback"><span>判断准确吗？</span><button onClick={() => submitFeedback(true)}><ThumbsUp />准确</button><button onClick={() => submitFeedback(false)}><ThumbsDown />{result.class_id ? "误报：应为正常" : "漏报：应为风险"}</button>{feedback && <b>{feedback}</b>}</div></div>}</article></section>
        <HistoryTable rows={history.slice(0, 5)} onMore={() => setView("history")} /></>}
      {view === "batch" && <BatchView analyze={analyze} />}{view === "history" && <HistoryTable rows={history} clear={() => setHistory([])} />}{view === "model" && <ModelView health={health} />}
    </main>
  </div>;
}

function HistoryTable({ rows, onMore, clear }) {
  return <section className="panel history-panel"><div className="panel-title"><div><span className="step">03</span><h2>最近检测记录</h2></div>{clear ? <button className="ghost" onClick={clear}><Trash />清空记录</button> : <button className="ghost" onClick={onMore}>查看全部</button>}</div><div className="table-wrap"><table><thead><tr><th>时间</th><th>信息摘要</th><th>判断结果</th><th>风险概率</th><th>类型</th></tr></thead><tbody>{rows.map((row, i) => <tr key={`${row.time}-${i}`}><td>{row.time}</td><td>{row.text}</td><td><span className={`status ${row.label === "风险短信" ? "risk" : "normal"}`}>{row.label}</span></td><td><div className="mini-score"><i style={{ width: `${row.score / 2}px` }} /><span>{row.score}%</span></div></td><td>{row.category}</td></tr>)}</tbody></table>{!rows.length && <div className="empty-table">暂无检测记录</div>}</div></section>;
}
function BatchView({ analyze }) {
  const [batch, setBatch] = useState(samples.map(x => x[1]).join("\n"));
  return <section className="panel standalone"><div className="panel-title"><div><span className="step">BATCH</span><h2>批量扫描</h2></div></div><p className="lead">每行一条信息，快速挑出需要优先处理的风险内容。</p><textarea value={batch} onChange={e => setBatch(e.target.value)} /><button className="primary" onClick={() => batch.split("\n").filter(Boolean).forEach((x, i) => setTimeout(() => analyze(x), i * 250))}><ListChecks />开始批量扫描</button></section>;
}
function ModelView({ health }) {
  const values = health ? [["测试集准确率", health.test_accuracy, "对已标注测试数据的整体判断准确程度"], ["风险召回率", health.risk_recall, "实际风险信息中成功识别出的比例"], ["正常误报率", health.false_positive_rate, "正常信息被误判为风险的比例"]] : [];
  return <section className="model-view"><article className="panel model-intro"><Database size={36} /><div><span className="eyebrow">HYBRID ENGINE</span><h2>白马卫士 Hybrid Guard v1.2</h2><p>字符级 RNN、扩展风险策略与持久化反馈学习共同判断。当前已学习 {health?.feedback_count || 0} 条用户反馈。</p></div></article><div className="model-cards">{values.map(([label, value, note]) => <article className="panel" key={label}><span>{label}</span><strong>{(value * 100).toFixed(1)}%</strong><div className="model-bar"><i style={{ width: `${value * 100}%` }} /></div><p>{note}</p></article>)}</div></section>;
}
