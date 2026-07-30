import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { api, RemoteSkillItem } from '../api';

// 社区知名 Skills 源快选列表
const COMMUNITY_SOURCES = [
  {
    label: 'obra/superpowers',
    emoji: '⚡',
    stars: '66.9k',
    desc: '完整开发工作流技能集',
    skills: [
      { name: 'brainstorming', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/brainstorming/SKILL.md' },
      { name: 'test-driven-development', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/test-driven-development/SKILL.md' },
      { name: 'systematic-debugging', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/systematic-debugging/SKILL.md' },
      { name: 'subagent-driven-development', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/subagent-driven-development/SKILL.md' },
      { name: 'writing-plans', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/writing-plans/SKILL.md' },
      { name: 'executing-plans', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/executing-plans/SKILL.md' },
      { name: 'requesting-code-review', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/requesting-code-review/SKILL.md' },
      { name: 'root-cause-tracing', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/root-cause-tracing/SKILL.md' },
      { name: 'verification-before-completion', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/verification-before-completion/SKILL.md' },
      { name: 'dispatching-parallel-agents', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/dispatching-parallel-agents/SKILL.md' },
    ],
  },
  {
    label: 'anthropics/skills',
    emoji: '🏛️',
    stars: '官方',
    desc: 'Anthropic 官方技能库',
    skills: [
      { name: 'docx', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/docx/SKILL.md' },
      { name: 'pdf', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/pdf/SKILL.md' },
      { name: 'xlsx', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/xlsx/SKILL.md' },
      { name: 'pptx', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/pptx/SKILL.md' },
      { name: 'mcp-builder', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/mcp-builder/SKILL.md' },
      { name: 'frontend-design', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md' },
      { name: 'web-artifacts-builder', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/web-artifacts-builder/SKILL.md' },
      { name: 'webapp-testing', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/webapp-testing/SKILL.md' },
      { name: 'algorithmic-art', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/algorithmic-art/SKILL.md' },
      { name: 'canvas-design', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/canvas-design/SKILL.md' },
    ],
  },
  {
    label: 'ComposioHQ/awesome-claude-skills',
    emoji: '🌐',
    stars: '39.2k',
    desc: '100+ 社区精选技能',
    skills: [
      { name: 'github-integration', url: 'https://raw.githubusercontent.com/ComposioHQ/awesome-claude-skills/master/github-integration/SKILL.md' },
      { name: 'data-analysis', url: 'https://raw.githubusercontent.com/ComposioHQ/awesome-claude-skills/master/data-analysis/SKILL.md' },
      { name: 'code-review', url: 'https://raw.githubusercontent.com/ComposioHQ/awesome-claude-skills/master/code-review/SKILL.md' },
    ],
  },
];

// ── 帮助函数 ──

/** 给 emoji 上色用的色盘 */
const EMOJI_BG: Record<string, string> = {
  '🧠': '#0d1f45', '🤖': '#3d1111', '🕴️': '#0a3322',
  '🏛️': '#0d1f45', '📜': '#3d2a0a', '🔍': '#0a2a3d',
  '📮': '#2a1a3d', '📝': '#2a3d1a', '⚔️': '#3d1a1a',
  '🎨': '#1a2a3d', '⚖️': '#1a3d2a', '📋': '#2a2a1a',
};

function agentAccent(emoji = '🧠'): string {
  return EMOJI_BG[emoji] || '#1a1a2e';
}

type SkillItem = {
  name: string;
  title?: string;
  path?: string;
  exists?: boolean;
  description?: string;
  isGlobal?: boolean;
  enabled?: boolean;
};

type AgentInfo = {
  id: string;
  label: string;
  emoji: string;
  skills?: SkillItem[];
};

type GlobalSkillInfo = {
  name: string;
  description?: string;
  path: string;
  isGlobal?: boolean;
};

export default function SkillsConfig() {
  const agentConfig = useStore((s) => s.agentConfig);
  const loadAgentConfig = useStore((s) => s.loadAgentConfig);
  const toast = useStore((s) => s.toast);

  // 技能查看弹窗
  const [skillModal, setSkillModal] = useState<{ agentId: string; name: string; content: string; path: string } | null>(null);
  // 添加私有技能弹窗
  const [addForm, setAddForm] = useState<{ agentId: string; agentLabel: string } | null>(null);
  const [formData, setFormData] = useState({ name: '', desc: '', trigger: '' });
  const [submitting, setSubmitting] = useState(false);
  // Toggle 状态
  const [toggling, setToggling] = useState<string | null>(null);

  // 主 Tab 切换
  const [activeTab, setActiveTab] = useState<'local' | 'remote'>('local');

  // 远程技能状态
  const [remoteSkills, setRemoteSkills] = useState<RemoteSkillItem[]>([]);
  const [remoteLoading, setRemoteLoading] = useState(false);
  const [addRemoteForm, setAddRemoteForm] = useState(false);
  const [remoteFormData, setRemoteFormData] = useState({ agentId: '', skillName: '', sourceUrl: '', description: '' });
  const [remoteSubmitting, setRemoteSubmitting] = useState(false);
  const [updatingSkill, setUpdatingSkill] = useState<string | null>(null);
  const [removingSkill, setRemovingSkill] = useState<string | null>(null);
  const [quickPickSource, setQuickPickSource] = useState<(typeof COMMUNITY_SOURCES)[0] | null>(null);
  const [quickPickAgent, setQuickPickAgent] = useState('');

  useEffect(() => {
    loadAgentConfig();
  }, [loadAgentConfig]);

  useEffect(() => {
    if (activeTab === 'remote') loadRemoteSkills();
  }, [activeTab]);

  const loadRemoteSkills = async () => {
    setRemoteLoading(true);
    try {
      const r = await api.remoteSkillsList();
      if (r.ok) setRemoteSkills(r.remoteSkills || []);
    } catch {
      toast('远程技能列表加载失败', 'err');
    }
    setRemoteLoading(false);
  };

  const openSkill = async (agentId: string, skillName: string) => {
    setSkillModal({ agentId, name: skillName, content: '⟳ 加载中…', path: '' });
    try {
      const r = await api.skillContent(agentId, skillName);
      if (r.ok) {
        setSkillModal({ agentId, name: skillName, content: r.content || '', path: r.path || '' });
      } else {
        setSkillModal({ agentId, name: skillName, content: '❌ ' + (r.error || '无法读取'), path: '' });
      }
    } catch {
      setSkillModal({ agentId, name: skillName, content: '❌ 服务器连接失败', path: '' });
    }
  };

  const toggleSkill = async (agentId: string, skillName: string, enabled: boolean) => {
    const key = `${agentId}/${skillName}`;
    setToggling(key);
    try {
      const r = await api.toggleGlobalSkill(agentId, skillName, enabled);
      if (r.ok) {
        toast(`✅ ${enabled ? '启用' : '禁用'} ${skillName}`, 'ok');
        loadAgentConfig();
      } else {
        toast(r.error || '操作失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
    setToggling(null);
  };

  const openAddForm = (agentId: string, agentLabel: string) => {
    setAddForm({ agentId, agentLabel });
    setFormData({ name: '', desc: '', trigger: '' });
  };

  const submitAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addForm || !formData.name) return;
    setSubmitting(true);
    try {
      const r = await api.addSkill(addForm.agentId, formData.name, formData.desc, formData.trigger);
      if (r.ok) {
        toast(`✅ 私有技能 ${formData.name} 已添加到 ${addForm.agentLabel}`, 'ok');
        setAddForm(null);
        loadAgentConfig();
      } else {
        toast(r.error || '添加失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
    setSubmitting(false);
  };

  const submitAddRemote = async (e: React.FormEvent) => {
    e.preventDefault();
    const { agentId, skillName, sourceUrl, description } = remoteFormData;
    if (!agentId || !skillName || !sourceUrl) return;
    setRemoteSubmitting(true);
    try {
      const r = await api.addRemoteSkill(agentId, skillName, sourceUrl, description);
      if (r.ok) {
        toast(`✅ 远程技能 ${skillName} 已添加到 ${agentId}`, 'ok');
        setAddRemoteForm(false);
        setRemoteFormData({ agentId: '', skillName: '', sourceUrl: '', description: '' });
        loadRemoteSkills();
        loadAgentConfig();
      } else {
        toast(r.error || '添加失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
    setRemoteSubmitting(false);
  };

  const handleUpdate = async (skill: RemoteSkillItem) => {
    const key = `${skill.agentId}/${skill.skillName}`;
    setUpdatingSkill(key);
    try {
      const r = await api.updateRemoteSkill(skill.agentId, skill.skillName);
      if (r.ok) {
        toast(`✅ 技能 ${skill.skillName} 已更新`, 'ok');
        loadRemoteSkills();
      } else {
        toast(r.error || '更新失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
    setUpdatingSkill(null);
  };

  const handleRemove = async (skill: RemoteSkillItem) => {
    const key = `${skill.agentId}/${skill.skillName}`;
    setRemovingSkill(key);
    try {
      const r = await api.removeRemoteSkill(skill.agentId, skill.skillName);
      if (r.ok) {
        toast(`🗑️ 技能 ${skill.skillName} 已移除`, 'ok');
        loadRemoteSkills();
        loadAgentConfig();
      } else {
        toast(r.error || '移除失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
    setRemovingSkill(null);
  };

  const handleQuickImport = async (skillUrl: string, skillName: string) => {
    if (!quickPickAgent) { toast('请先选择目标 Agent', 'err'); return; }
    try {
      const r = await api.addRemoteSkill(quickPickAgent, skillName, skillUrl, '');
      if (r.ok) {
        toast(`✅ ${skillName} → ${quickPickAgent}`, 'ok');
        loadRemoteSkills();
        loadAgentConfig();
      } else {
        toast(r.error || '导入失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
  };

  if (!agentConfig?.agents) {
    return <div className="empty">无法加载</div>;
  }

  // ── 全局技能池统计 ──
  const globalPool: GlobalSkillInfo[] = agentConfig.globalSkillsPool || [];
  const totalGlobal = globalPool.length;

  // ── 本地技能面板（全局池 + 私有技能）──
  const localPanel = (
    <div>
      {/* 全局技能池总览 */}
      {globalPool.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{
            fontSize: 12, fontWeight: 700, color: 'var(--muted)',
            letterSpacing: '.06em', marginBottom: 12,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            🏛️ 全局技能池
            <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 999, background: '#0d1f45', color: 'var(--acc)' }}>
              {totalGlobal} 个
            </span>
            <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400, marginLeft: 4 }}>
              — 所有 Agent 共享，在下面各 Agent 卡中开启/关闭
            </span>
          </div>

          {/* 全局技能预览条 */}
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 4,
            background: 'var(--panel)', borderRadius: 12, border: '1px solid var(--line)',
            padding: '10px 14px',
          }}>
            {globalPool.map((sk) => (
              <span key={sk.name} style={{
                fontSize: 10, padding: '2px 8px', borderRadius: 999,
                background: '#0a1a2e', color: '#7ab7ff',
              }}>
                📦 {sk.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Agent 卡片 — 每个 Agent 显示其技能列表 */}
      <div className="skills-grid">
        {agentConfig.agents.map((ag) => {
          const skills = (ag.skills || []) as SkillItem[];
          const globalSkills = skills.filter((s) => s.isGlobal);
          const customSkills = skills.filter((s) => !s.isGlobal);
          const enabledCount = globalSkills.filter((s) => s.enabled).length;

          return (
            <div className="sk-card" key={ag.id}>
              {/* Agent 头部 */}
              <div className="sk-hdr">
                <span className="sk-emoji">{ag.emoji || '🏛️'}</span>
                <span className="sk-name">{ag.label}</span>
                <span className="sk-cnt">
                  {enabledCount}/{totalGlobal} 启用
                  {customSkills.length > 0 && ` · +${customSkills.length} 私有`}
                </span>
              </div>

              {/* 全局技能列表 */}
              <div className="sk-list">
                <div style={{
                  fontSize: 10, fontWeight: 600, color: 'var(--muted)',
                  letterSpacing: '.04em', padding: '6px 10px 4px',
                }}>
                  全局技能
                </div>
                {globalSkills.length === 0 ? (
                  <div className="sk-empty">加载中…</div>
                ) : (
                  globalSkills.map((sk) => {
                    const key = `${ag.id}/${sk.name}`;
                    const isToggling = toggling === key;
                    return (
                      <div
                        className={`sk-item ${sk.enabled ? 'sk-item-on' : ''}`}
                        key={sk.name}
                        style={{ opacity: sk.enabled ? 1 : 0.5 }}
                      >
                        {/* 点击标题查看详情 */}
                        <span
                          className="si-name"
                          onClick={() => openSkill(ag.id, sk.name)}
                          style={{ cursor: 'pointer', flex: 1 }}
                        >
                          📦 {sk.name}
                        </span>
                        <span className="si-desc">{sk.description || ''}</span>
                        {/* Toggle 开关 */}
                        <button
                          onClick={() => toggleSkill(ag.id, sk.name, !sk.enabled)}
                          disabled={isToggling}
                          style={{
                            flexShrink: 0, width: 36, height: 20, borderRadius: 999, border: 'none',
                            cursor: 'pointer', position: 'relative', transition: 'all .2s',
                            background: sk.enabled ? '#4caf88' : '#3a3a4a',
                            padding: 0,
                          }}
                          title={sk.enabled ? '点击禁用' : '点击启用'}
                        >
                          <span style={{
                            position: 'absolute', top: 2, width: 16, height: 16, borderRadius: '50%',
                            background: '#fff', transition: 'all .2s',
                            left: sk.enabled ? 18 : 2,
                            opacity: isToggling ? 0.4 : 1,
                          }} />
                        </button>
                      </div>
                    );
                  })
                )}

                {/* 私有技能列表 */}
                {customSkills.length > 0 && (
                  <>
                    <div style={{
                      fontSize: 10, fontWeight: 600, color: 'var(--acc)',
                      letterSpacing: '.04em', padding: '10px 10px 4px',
                      borderTop: '1px solid var(--line)',
                      marginTop: 4,
                    }}>
                      🔧 私有技能
                    </div>
                    {customSkills.map((sk) => (
                      <div className="sk-item" key={sk.name}>
                        <span
                          className="si-name"
                          onClick={() => openSkill(ag.id, sk.name)}
                          style={{ cursor: 'pointer' }}
                        >
                          🔧 {sk.name}
                        </span>
                        <span className="si-desc">{sk.description || ''}</span>
                        <span className="si-arrow">›</span>
                      </div>
                    ))}
                  </>
                )}
              </div>

              {/* 添加私有技能按钮 */}
              <div className="sk-add" onClick={() => openAddForm(ag.id, ag.label)}>
                ＋ 添加私有技能
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );

  // ── 远程技能面板（不变）──
  const remotePanel = (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <button
          style={{ padding: '8px 18px', background: 'var(--acc)', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13 }}
          onClick={() => { setAddRemoteForm(true); setQuickPickSource(null); }}
        >
          ＋ 添加远程 Skill
        </button>
        <button
          style={{ padding: '8px 14px', background: 'transparent', color: 'var(--acc)', border: '1px solid var(--acc)', borderRadius: 8, cursor: 'pointer', fontSize: 12 }}
          onClick={loadRemoteSkills}
        >
          ⟳ 刷新列表
        </button>
        <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 4 }}>
          共 {remoteSkills.length} 个远程技能
        </span>
      </div>

      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', letterSpacing: '.06em', marginBottom: 10 }}>
          🌐 社区技能源 — 一键导入
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {COMMUNITY_SOURCES.map((src) => (
            <div
              key={src.label}
              onClick={() => setQuickPickSource(quickPickSource?.label === src.label ? null : src)}
              style={{
                padding: '8px 14px',
                background: quickPickSource?.label === src.label ? '#0d1f45' : 'var(--panel)',
                border: `1px solid ${quickPickSource?.label === src.label ? 'var(--acc)' : 'var(--line)'}`,
                borderRadius: 10,
                cursor: 'pointer',
                fontSize: 12,
                transition: 'all .15s',
              }}
            >
              <span style={{ marginRight: 6 }}>{src.emoji}</span>
              <b style={{ color: 'var(--text)' }}>{src.label}</b>
              <span style={{ marginLeft: 6, color: '#f0b429', fontSize: 11 }}>★ {src.stars}</span>
              <span style={{ marginLeft: 8, color: 'var(--muted)' }}>{src.desc}</span>
            </div>
          ))}
        </div>

        {quickPickSource && (
          <div style={{ marginTop: 14, background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 12, padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
              <span style={{ fontSize: 12, fontWeight: 600 }}>目标 Agent：</span>
              <select
                value={quickPickAgent}
                onChange={(e) => setQuickPickAgent(e.target.value)}
                style={{ padding: '6px 10px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 6, color: 'var(--text)', fontSize: 12 }}
              >
                <option value="">— 选择 Agent —</option>
                {agentConfig.agents.map((ag) => (
                  <option key={ag.id} value={ag.id}>{ag.emoji} {ag.label} ({ag.id})</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 8 }}>
              {quickPickSource.skills.map((sk) => {
                const alreadyAdded = remoteSkills.some((r) => r.skillName === sk.name && r.agentId === quickPickAgent);
                return (
                  <div
                    key={sk.name}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '8px 12px', background: 'var(--panel2)', borderRadius: 8,
                      border: '1px solid var(--line)',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>📦 {sk.name}</div>
                      <div style={{ fontSize: 10, color: 'var(--muted)', wordBreak: 'break-all', maxWidth: 180 }}>{sk.url.split('/').slice(-2).join('/')}</div>
                    </div>
                    {alreadyAdded ? (
                      <span style={{ fontSize: 10, color: '#4caf88', fontWeight: 600 }}>✓ 已导入</span>
                    ) : (
                      <button
                        onClick={() => handleQuickImport(sk.url, sk.name)}
                        style={{ padding: '4px 10px', background: 'var(--acc)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 11, whiteSpace: 'nowrap' }}
                      >
                        导入
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {remoteLoading ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13 }}>⟳ 加载中…</div>
      ) : remoteSkills.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px', background: 'var(--panel)', borderRadius: 12, border: '1px dashed var(--line)' }}>
          <div style={{ fontSize: 32, marginBottom: 10 }}>🌐</div>
          <div style={{ fontSize: 14, color: 'var(--muted)' }}>尚无远程技能</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 6 }}>从社区技能源快速导入，或手动添加 URL</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {remoteSkills.map((sk) => {
            const key = `${sk.agentId}/${sk.skillName}`;
            const isUpdating = updatingSkill === key;
            const isRemoving = removingSkill === key;
            const agInfo = agentConfig.agents.find((a) => a.id === sk.agentId);
            return (
              <div
                key={key}
                style={{
                  background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 12, padding: '14px 18px',
                  display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <span style={{ fontSize: 14, fontWeight: 700 }}>📦 {sk.skillName}</span>
                    <span style={{
                      fontSize: 10, padding: '2px 8px', borderRadius: 999,
                      background: sk.status === 'valid' ? '#0d3322' : '#3d1111',
                      color: sk.status === 'valid' ? '#4caf88' : '#ff5270',
                      fontWeight: 600,
                    }}>
                      {sk.status === 'valid' ? '✓ 有效' : '✗ 文件丢失'}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--panel2)', padding: '2px 8px', borderRadius: 6 }}>
                      {agInfo?.emoji} {agInfo?.label || sk.agentId}
                    </span>
                  </div>
                  {sk.description && (
                    <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>{sk.description}</div>
                  )}
                  <div style={{ fontSize: 10, color: 'var(--muted)', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                    <span>🔗 <a href={sk.sourceUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--acc)', textDecoration: 'none' }}>{sk.sourceUrl.length > 60 ? sk.sourceUrl.slice(0, 60) + '…' : sk.sourceUrl}</a></span>
                    <span>📅 {sk.lastUpdated ? sk.lastUpdated.slice(0, 10) : sk.addedAt?.slice(0, 10)}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    onClick={() => openSkill(sk.agentId, sk.skillName)}
                    style={{ padding: '6px 12px', background: 'transparent', color: 'var(--muted)', border: '1px solid var(--line)', borderRadius: 6, cursor: 'pointer', fontSize: 11 }}
                  >
                    查看
                  </button>
                  <button
                    onClick={() => handleUpdate(sk)}
                    disabled={isUpdating}
                    style={{ padding: '6px 12px', background: 'transparent', color: 'var(--acc)', border: '1px solid var(--acc)', borderRadius: 6, cursor: 'pointer', fontSize: 11 }}
                  >
                    {isUpdating ? '⟳' : '更新'}
                  </button>
                  <button
                    onClick={() => handleRemove(sk)}
                    disabled={isRemoving}
                    style={{ padding: '6px 12px', background: 'transparent', color: '#ff5270', border: '1px solid #ff5270', borderRadius: 6, cursor: 'pointer', fontSize: 11 }}
                  >
                    {isRemoving ? '⟳' : '删除'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  return (
    <div>
      {/* 主 Tab 切换 */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--line)', paddingBottom: 0 }}>
        {[
          {
            key: 'local',
            label: '🏛️ 本地技能',
            count: agentConfig.agents.reduce(
              (n, a) => n + ((a.skills || []) as SkillItem[]).filter((s) => !s.isGlobal).length,
              0
            ),
            sub: `池:${totalGlobal}`,
          },
          { key: 'remote', label: '🌐 远程技能', count: remoteSkills.length },
        ].map((t) => (
          <div
            key={t.key}
            onClick={() => setActiveTab(t.key as 'local' | 'remote')}
            style={{
              padding: '8px 18px', cursor: 'pointer', fontSize: 13, borderRadius: '8px 8px 0 0',
              fontWeight: activeTab === t.key ? 700 : 400,
              background: activeTab === t.key ? 'var(--panel)' : 'transparent',
              color: activeTab === t.key ? 'var(--text)' : 'var(--muted)',
              border: activeTab === t.key ? '1px solid var(--line)' : '1px solid transparent',
              borderBottom: activeTab === t.key ? '1px solid var(--panel)' : '1px solid transparent',
              position: 'relative', bottom: -1,
              transition: 'all .15s',
            }}
          >
            {t.label}
            {t.sub && (
              <span style={{ marginLeft: 6, fontSize: 10, color: '#7ab7ff' }}>
                {t.sub}
              </span>
            )}
            {t.count > 0 && (
              <span style={{ marginLeft: 6, fontSize: 10, padding: '1px 6px', borderRadius: 999, background: '#1a2040', color: 'var(--acc)' }}>
                {t.count}
              </span>
            )}
          </div>
        ))}
      </div>

      {activeTab === 'local' ? localPanel : remotePanel}

      {/* Skill Content Modal */}
      {skillModal && (
        <div className="modal-bg open" onClick={() => setSkillModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setSkillModal(null)}>✕</button>
            <div className="modal-body">
              <div style={{ fontSize: 11, color: 'var(--acc)', fontWeight: 700, letterSpacing: '.04em', marginBottom: 4 }}>
                {skillModal.agentId.toUpperCase()}
              </div>
              <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 16 }}>📦 {skillModal.name}</div>
              <div className="sk-modal-body">
                <div className="sk-md" style={{ whiteSpace: 'pre-wrap', fontSize: 12, lineHeight: 1.7 }}>
                  {skillModal.content}
                </div>
                {skillModal.path && (
                  <div className="sk-path" style={{ fontSize: 10, color: 'var(--muted)', marginTop: 12 }}>
                    📂 {skillModal.path}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 本地 Add Skill Form Modal */}
      {addForm && (
        <div className="modal-bg open" onClick={() => setAddForm(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setAddForm(null)}>✕</button>
            <div className="modal-body">
              <div style={{ fontSize: 11, color: 'var(--acc)', fontWeight: 700, letterSpacing: '.04em', marginBottom: 4 }}>
                为 {addForm.agentLabel} 添加私有技能
              </div>
              <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 18 }}>⚙️ 新增私有 Skill</div>

              <div
                style={{
                  background: 'var(--panel2)',
                  border: '1px solid var(--line)',
                  borderRadius: 10,
                  padding: 14,
                  marginBottom: 18,
                  fontSize: 12,
                  lineHeight: 1.7,
                  color: 'var(--muted)',
                }}
              >
                <b style={{ color: 'var(--text)' }}>📋 私有技能 vs 全局技能</b>
                <br />
                全局技能（如 brainstorm, TDD）已自动共享给所有 Agent，直接在卡片里开关即可。
                <br />
                如果某个 Agent 需要<b style={{ color: 'var(--text)' }}>仅此一家</b>的独特技能，在这里创建。
              </div>

              <form onSubmit={submitAdd} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>
                    技能名称 <span style={{ color: '#ff5270' }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="如 data-analysis, code-review"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData((p) => ({ ...p, name: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') }))
                    }
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13, outline: 'none' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>技能描述</label>
                  <input
                    type="text"
                    placeholder="一句话说明用途"
                    value={formData.desc}
                    onChange={(e) => setFormData((p) => ({ ...p, desc: e.target.value }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13, outline: 'none' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>触发条件（可选）</label>
                  <input
                    type="text"
                    placeholder="何时激活此技能"
                    value={formData.trigger}
                    onChange={(e) => setFormData((p) => ({ ...p, trigger: e.target.value }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13, outline: 'none' }}
                  />
                </div>
                <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 4 }}>
                  <button type="button" className="btn btn-g" onClick={() => setAddForm(null)} style={{ padding: '8px 20px' }}>
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    style={{ padding: '8px 20px', fontSize: 13, background: 'var(--acc)', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}
                  >
                    {submitting ? '⟳ 创建中…' : '⚙️ 创建私有技能'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* 远程 Add Remote Skill Modal */}
      {addRemoteForm && (
        <div className="modal-bg open" onClick={() => setAddRemoteForm(false)}>
          <div className="modal" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setAddRemoteForm(false)}>✕</button>
            <div className="modal-body">
              <div style={{ fontSize: 11, color: '#a07aff', fontWeight: 700, letterSpacing: '.04em', marginBottom: 4 }}>
                远程技能管理
              </div>
              <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 18 }}>🌐 添加远程 Skill</div>

              <div style={{ background: 'var(--panel2)', border: '1px solid var(--line)', borderRadius: 10, padding: 12, marginBottom: 18, fontSize: 11, color: 'var(--muted)', lineHeight: 1.7 }}>
                支持 GitHub Raw URL，如：<br />
                <code style={{ color: 'var(--acc)', fontSize: 10 }}>https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/brainstorming/SKILL.md</code>
              </div>

              <form onSubmit={submitAddRemote} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>目标 Agent <span style={{ color: '#ff5270' }}>*</span></label>
                  <select
                    required
                    value={remoteFormData.agentId}
                    onChange={(e) => setRemoteFormData((p) => ({ ...p, agentId: e.target.value }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }}
                  >
                    <option value="">— 选择 Agent —</option>
                    {agentConfig.agents.map((ag) => (
                      <option key={ag.id} value={ag.id}>{ag.emoji} {ag.label} ({ag.id})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>技能名称 <span style={{ color: '#ff5270' }}>*</span></label>
                  <input
                    type="text"
                    required
                    placeholder="如 brainstorming, code-review"
                    value={remoteFormData.skillName}
                    onChange={(e) => setRemoteFormData((p) => ({ ...p, skillName: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13, outline: 'none' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>源 URL <span style={{ color: '#ff5270' }}>*</span></label>
                  <input
                    type="url"
                    required
                    placeholder="https://raw.githubusercontent.com/..."
                    value={remoteFormData.sourceUrl}
                    onChange={(e) => setRemoteFormData((p) => ({ ...p, sourceUrl: e.target.value }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 12, outline: 'none' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>描述（可选）</label>
                  <input
                    type="text"
                    placeholder="一句话说明用途"
                    value={remoteFormData.description}
                    onChange={(e) => setRemoteFormData((p) => ({ ...p, description: e.target.value }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13, outline: 'none' }}
                  />
                </div>
                <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 4 }}>
                  <button type="button" className="btn btn-g" onClick={() => setAddRemoteForm(false)} style={{ padding: '8px 20px' }}>取消</button>
                  <button
                    type="submit"
                    disabled={remoteSubmitting}
                    style={{ padding: '8px 20px', fontSize: 13, background: '#a07aff', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}
                  >
                    {remoteSubmitting ? '⟳ 下载中…' : '🌐 添加远程技能'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
