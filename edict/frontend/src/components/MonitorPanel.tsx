import { useEffect } from 'react';
import { useStore, DEPTS, isEdict, stateLabel } from '../store';
import { api, type OfficialInfo } from '../api';

export default function MonitorPanel() {
  const liveStatus = useStore((s) => s.liveStatus);
  const agentsStatusData = useStore((s) => s.agentsStatusData);
  const officialsData = useStore((s) => s.officialsData);
  const loadAgentsStatus = useStore((s) => s.loadAgentsStatus);
  const setModalTaskId = useStore((s) => s.setModalTaskId);
  const toast = useStore((s) => s.toast);

  useEffect(() => {
    loadAgentsStatus();
  }, [loadAgentsStatus]);

  const tasks = liveStatus?.tasks || [];
  const activeTasks = tasks.filter((t) => isEdict(t) && t.state !== 'Done' && t.state !== 'Next' && t.state !== 'Cancelled');

  // Build official map
  const offMap: Record<string, OfficialInfo> = {};
  if (officialsData?.officials) {
    officialsData.officials.forEach((o) => { offMap[o.id] = o; });
  }

  // Agent wake
  const handleWake = async (agentId: string) => {
    try {
      const r = await api.agentWake(agentId);
      toast(r.message || '唤醒指令已发出');
      setTimeout(() => loadAgentsStatus(), 30000);
    } catch { toast('唤醒失败', 'err'); }
  };

  const handleWakeAll = async () => {
    if (!agentsStatusData) return;
    const toWake = agentsStatusData.agents.filter(
      (a) => a.status !== 'running' && a.status !== 'unconfigured'
    );
    if (!toWake.length) { toast('所有 Agent 均已在线'); return; }
    toast(`正在唤醒 ${toWake.length} 个 Agent...`);
    for (const a of toWake) {
      try { await api.agentWake(a.id); } catch { /* ignore */ }
    }
    toast(`${toWake.length} 个唤醒指令已发出，30秒后刷新状态`);
    setTimeout(() => loadAgentsStatus(), 30000);
  };

  // Agent Status Panel
  const asData = agentsStatusData;
  const agents = asData?.agents || [];
  const courtCoverage = asData?.courtCoverage || [];
  const running = agents.filter((a) => a.status === 'running').length;
  const idle = agents.filter((a) => a.status === 'idle').length;
  const offline = agents.filter((a) => a.status === 'offline').length;
  const unconf = agents.filter((a) => a.status === 'unconfigured').length;
  const gw = asData?.gateway;
  const gwCls = gw?.probe ? 'ok' : gw?.alive ? 'warn' : 'err';

  return (
    <div>
      {/* Agent Status Panel — 运行时 Agent */}
      {asData && asData.ok && (
        <div className="as-panel">
          <div className="as-header">
            <span className="as-title">🔌 运行时 Agent 状态</span>
            <span className={`as-gw ${gwCls}`}>Gateway: {gw?.status || '未知'}</span>
            <button className="btn-refresh" onClick={() => loadAgentsStatus()} style={{ marginLeft: 8 }}>
              🔄 刷新
            </button>
            {(offline + unconf > 0) && (
              <button className="btn-refresh" onClick={handleWakeAll} style={{ marginLeft: 4, borderColor: 'var(--warn)', color: 'var(--warn)' }}>
                ⚡ 全部唤醒
              </button>
            )}
          </div>
          <div className="as-grid">
            {agents.map((a) => {
              const canWake = a.status !== 'running' && a.status !== 'unconfigured' && gw?.alive;
              const roleSuffix = a.courtTitle ? ` · ${a.courtTitle}` : '';
              return (
                <div key={a.id} className="as-card" title={`${a.role}${roleSuffix} · ${a.statusLabel}`}>
                  <div className={`as-dot ${a.status}`} />
                  <div style={{ fontSize: 22 }}>{a.emoji}</div>
                  <div style={{ fontSize: 12, fontWeight: 700 }}>{a.label}</div>
                  <div style={{ fontSize: 10, color: 'var(--muted)' }}>
                    {a.role}{roleSuffix ? <span style={{ fontSize: 9, color: 'var(--muted)' }}>{roleSuffix}</span> : ''}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--muted)' }}>{a.statusLabel}</div>
                  {a.lastActive ? (
                    <div style={{ fontSize: 10, color: 'var(--muted)' }}>⏰ {a.lastActive}</div>
                  ) : (
                    <div style={{ fontSize: 10, color: 'var(--muted)' }}>无活动记录</div>
                  )}
                  {canWake && (
                    <button className="as-wake-btn" onClick={(e) => { e.stopPropagation(); handleWake(a.id); }}>
                      ⚡ 唤醒
                    </button>
                  )}
                </div>
              );
            })}
          </div>
          <div className="as-summary">
            <span><span className="as-dot running" style={{ position: 'static', width: 8, height: 8 }} /> {running} 运行中</span>
            <span><span className="as-dot idle" style={{ position: 'static', width: 8, height: 8 }} /> {idle} 待命</span>
            {offline > 0 && <span><span className="as-dot offline" style={{ position: 'static', width: 8, height: 8 }} /> {offline} 离线</span>}
            {unconf > 0 && <span><span className="as-dot unconfigured" style={{ position: 'static', width: 8, height: 8 }} /> {unconf} 未配置</span>}
            <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--muted)' }}>
              检测于 {(asData.checkedAt || '').substring(11, 19)}
            </span>
          </div>
        </div>
      )}

      {/* 官制覆盖面板 */}
      {courtCoverage.length > 0 && (
        <div className="as-panel">
          <div className="as-header">
            <span className="as-title" style={{ fontSize: 13 }}>🏛️ 三省六部 · 官制覆盖</span>
            <span style={{ fontSize: 10, color: 'var(--muted)' }}>
              {courtCoverage.filter(c => c.covered === 'covered').length}/{courtCoverage.length} 部已配置
            </span>
          </div>
          <div className="as-grid">
            {courtCoverage.map((c) => {
              const covCls = c.covered === 'covered' ? 'running' : 'unconfigured';
              const agentLabel = c.agentName ? `${c.agentName}(${c.agentId})` : '（未配置）';
              const statLabel = c.covered === 'covered'
                ? (c.agentStatus === 'running' ? '🟢 在线' : c.agentStatus === 'idle' ? '⚪ 待命' : '🔴 离线')
                : '❌ 未配置';
              return (
                <div key={c.id} className="as-card" title={`${c.label} → ${agentLabel}`}>
                  <div className={`as-dot ${covCls}`} style={c.covered === 'covered' ? { boxShadow: '0 0 6px #2ecc8a88' } : {}} />
                  <div style={{ fontSize: 22 }}>{c.emoji}</div>
                  <div style={{ fontSize: 11, fontWeight: 700 }}>{c.label}</div>
                  <div style={{ fontSize: 9, color: 'var(--muted)' }}>{agentLabel}</div>
                  <div style={{ fontSize: 9, color: 'var(--muted)' }}>{statLabel}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Duty Grid */}
      <div className="duty-grid">
        {DEPTS.map((d) => {
          // 从 courtCoverage 获取关联 Agent
          const court = courtCoverage.find(c => c.id === d.id);
          const agentName = court?.agentName || '';
          const covered = court?.covered === 'covered';

          const myTasks = activeTasks.filter((t) => t.org === d.label);
          const isActive = myTasks.some((t) => t.state === 'Doing');
          const isBlocked = myTasks.some((t) => t.state === 'Blocked');
          const off = offMap[d.id];
          const hb = off?.heartbeat || { status: 'idle', label: '⚪' };
          const dotCls = isBlocked ? 'blocked' : isActive ? 'busy' : hb.status === 'active' ? 'active' : 'idle';
          const statusText = isBlocked ? '⚠️ 阻塞' : isActive ? '⚙️ 执行中' : hb.status === 'active' ? '🟢 活跃' : '⚪ 候命';
          const cardCls = isBlocked ? 'blocked-card' : isActive ? 'active-card' : '';

          return (
            <div key={d.id} className={`duty-card ${cardCls}`}>
              <div className="dc-hdr">
                <span className="dc-emoji">{d.emoji}</span>
                <div className="dc-info">
                  <div className="dc-name">{d.label}</div>
                  <div className="dc-role">
                    {d.role} · {d.rank}
                    {covered
                      ? <span style={{ color: 'var(--ok)', fontSize: 10 }}> → {agentName}</span>
                      : <span style={{ color: 'var(--danger)', fontSize: 9 }}> 未配置</span>}
                  </div>
                </div>
                <div className="dc-status">
                  <span className={`dc-dot ${dotCls}`} />
                  <span>{statusText}</span>
                </div>
              </div>
              <div className="dc-body">
                {myTasks.length > 0 ? (
                  myTasks.map((t) => (
                    <div key={t.id} className="dc-task" onClick={() => setModalTaskId(t.id)}>
                      <div className="dc-task-id">{t.id}</div>
                      <div className="dc-task-title">{t.title || '(无标题)'}</div>
                      {t.now && t.now !== '-' && (
                        <div className="dc-task-now">{t.now.substring(0, 70)}</div>
                      )}
                      <div className="dc-task-meta">
                        <span className={`tag st-${t.state}`}>{stateLabel(t)}</span>
                        {t.block && t.block !== '无' && (
                          <span className="tag" style={{ borderColor: '#ff527044', color: 'var(--danger)' }}>🚫{t.block}</span>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="dc-idle">
                    <span style={{ fontSize: 20 }}>🪭</span>
                    <span>候命中</span>
                  </div>
                )}
              </div>
              <div className="dc-footer">
                <span className="dc-model">🤖 {agentName || off?.model_short || '待配置'}</span>
                {off?.last_active && <span className="dc-la">⏰ {off.last_active}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
