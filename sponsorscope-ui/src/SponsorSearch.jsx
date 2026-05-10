import { useState, useMemo, useEffect, useCallback } from 'react';
import { Search, MapPin, X, ArrowRight, Loader2, AlertCircle, Upload, FileText } from 'lucide-react';

// ============================================================
// API CONFIG
// ============================================================
// Change this if your backend runs elsewhere
const API_BASE = 'http://localhost:8000';

// ============================================================
// MOCK FALLBACK DATA (only used if API is unreachable)
// ============================================================
const MOCK_RESULTS = {
  results: [
    { employer: 'Google', count: 780, median: 196986, min: 150217, max: 244906, recent_date: '2026-05-10', months_ago: 0, city_list: ['Mountain View', 'Sunnyvale'], city_count: 2 },
    { employer: 'Apple', count: 608, median: 197936, min: 152000, max: 248000, recent_date: '2026-05-09', months_ago: 0, city_list: ['Cupertino', 'Sunnyvale'], city_count: 2 },
    { employer: 'Microsoft', count: 467, median: 191617, min: 148000, max: 235000, recent_date: '2026-05-08', months_ago: 0, city_list: ['Mountain View'], city_count: 1 },
    { employer: 'Amazon', count: 406, median: 186334, min: 145000, max: 230000, recent_date: '2026-05-07', months_ago: 0, city_list: ['San Francisco'], city_count: 1 },
    { employer: 'Meta', count: 342, median: 220730, min: 165000, max: 285000, recent_date: '2026-05-06', months_ago: 0, city_list: ['Menlo Park'], city_count: 1 },
  ],
  total: 5,
  stats: { total_companies: 5, total_filings: 2603, median_salary: 194759, new_hire_pct: 59 },
};
const MOCK_META = {
  categories: ['All', 'Software Engineer', 'Machine Learning Engineer', 'Data Scientist', 'Product Manager', 'Hardware Engineer'],
  states: ['All', 'CA', 'WA', 'NY', 'TX', 'NJ', 'MA', 'IL'],
  total_rows: 43730,
};

// Color system — light blue + white
const COLORS = {
  bg: '#ffffff', bgAlt: '#f8fbff', surface: '#ffffff',
  border: '#e4ecf7', borderStrong: '#c9dcef',
  primary: '#3b82f6', primaryDark: '#2563eb',
  primaryLight: '#dbeafe', primaryLighter: '#eff6ff',
  text: '#0f172a', textMuted: '#64748b', textLight: '#94a3b8',
  warning: '#f59e0b', warningLight: '#fef3c7',
};

const formatSalary = (n) => {
  if (!n || n <= 0) return '—';
  if (n > 2_000_000) return '—';   // outlier / bad data guard
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  return `$${Math.round(n / 1000)}K`;
};
const formatDate = (s) => s ? new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';

export default function SponsorScope() {
  const [category, setCategory] = useState('Software Engineer');
  const [state, setState] = useState('CA');
  const [sortBy, setSortBy] = useState('count');
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [companyDetail, setCompanyDetail] = useState(null);

  // API state
  const [meta, setMeta] = useState(null);
  const [searchData, setSearchData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [apiError, setApiError] = useState(null);
  const [usingMock, setUsingMock] = useState(false);

  // Resume upload state
  const [resumeFile, setResumeFile] = useState(null);
  const handleResumeUpload = (e) => {
    const file = e.target.files[0];
    if (file) setResumeFile(file);
  };

  // ----- Fetch metadata once on mount -----
  useEffect(() => {
    fetch(`${API_BASE}/meta`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setMeta(data);
        setApiError(null);
        setUsingMock(false);
      })
      .catch(err => {
        console.warn('API unreachable, falling back to mock data:', err.message);
        setMeta(MOCK_META);
        setApiError(err.message);
        setUsingMock(true);
      });
  }, []);

  // ----- Fetch search results when filters change -----
  const fetchResults = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ category, state, sort_by: sortBy, limit: '50' });
      const r = await fetch(`${API_BASE}/search?${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setSearchData(data);
      setApiError(null);
      setUsingMock(false);
    } catch (err) {
      console.warn('Search failed, using mock:', err.message);
      setSearchData(MOCK_RESULTS);
      setApiError(err.message);
      setUsingMock(true);
    } finally {
      setLoading(false);
    }
  }, [category, state, sortBy]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  // ----- Fetch company detail when row clicked -----
  const handleRowClick = async (company) => {
    setSelectedCompany(company);
    setCompanyDetail(null);
    setDetailLoading(true);
    try {
      const params = new URLSearchParams({ category, state });
      const r = await fetch(`${API_BASE}/company/${encodeURIComponent(company.employer)}?${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setCompanyDetail(data);
    } catch (err) {
      // Fallback: use what we already have from the search row
      setCompanyDetail({
        employer: company.employer,
        count: company.count,
        median: company.median,
        min: company.min,
        max: company.max,
        city_list: company.city_list,
        filings: [],
      });
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setSelectedCompany(null);
    setCompanyDetail(null);
  };

  const results = searchData?.results || [];
  const stats = searchData?.stats || { total_companies: 0, total_filings: 0, median_salary: 0, new_hire_pct: 0 };
  const categories = meta?.categories || ['All', 'Software Engineer'];
  const states = meta?.states || ['All', 'CA'];

  return (
    <div style={{ background: COLORS.bg, minHeight: '100vh', fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif', color: COLORS.text }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        * { box-sizing: border-box; }
        body { margin: 0; }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
        @keyframes spin { to { transform: rotate(360deg); } }
        .fade-row { animation: fadeUp 0.3s ease-out backwards; }
        .panel { animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
        .spin { animation: spin 0.8s linear infinite; }
        .row-hover { transition: all 0.15s ease; }
        .row-hover:hover { background: ${COLORS.primaryLighter} !important; }
        .row-hover:hover .arrow { opacity: 1 !important; transform: translateX(0) !important; color: ${COLORS.primary} !important; }
        .pill { transition: all 0.15s ease; }
        .pill:hover:not(.pill-active) { border-color: ${COLORS.primary} !important; color: ${COLORS.primary} !important; }
        .pill-active { background: ${COLORS.primary} !important; color: white !important; border-color: ${COLORS.primary} !important; }
        select { font-family: inherit; }
        select:focus { outline: none; }
        button:focus-visible, select:focus-visible { outline: 2px solid ${COLORS.primary}; outline-offset: 2px; }
        .search-btn:hover { background: ${COLORS.primaryDark} !important; }
        .close-btn:hover { background: ${COLORS.primaryLighter} !important; border-color: ${COLORS.primary} !important; }
        .resume-btn:hover { border-color: ${COLORS.primary} !important; color: ${COLORS.primary} !important; background: ${COLORS.primaryLighter} !important; }
      `}</style>

      {/* HEADER */}
      <header style={{
        borderBottom: `1px solid ${COLORS.border}`,
        padding: '20px 48px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: COLORS.bg,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <img
            src="data:image/png;base64,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"
            alt="SponsorSearch logo"
            style={{
              width: 36,
              height: 36,
              objectFit: 'contain',
              filter: 'brightness(0) saturate(100%) invert(37%) sepia(98%) saturate(1234%) hue-rotate(202deg) brightness(101%) contrast(97%)',
            }}
          />
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em' }}>
            SponsorSearch
          </h1>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {usingMock && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '4px 10px',
              background: COLORS.warningLight,
              border: `1px solid ${COLORS.warning}`,
              borderRadius: 6,
              fontSize: 12, fontWeight: 500, color: '#92400e',
            }}>
              <AlertCircle size={12} />
              Demo mode (API offline)
            </div>
          )}
          <div style={{ fontSize: 13, color: COLORS.textMuted, fontWeight: 500 }}>
            {meta?.total_rows ? `${meta.total_rows.toLocaleString()} LCA records` : 'Loading…'}
          </div>

          {/* Resume upload */}
          <label style={{ cursor: 'pointer' }}>
            <input
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={handleResumeUpload}
              style={{ display: 'none' }}
            />
            <div style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '8px 14px',
              background: resumeFile ? COLORS.primaryLighter : COLORS.bg,
              border: `1px solid ${resumeFile ? COLORS.primary : COLORS.border}`,
              borderRadius: 8,
              fontSize: 13, fontWeight: 500,
              color: resumeFile ? COLORS.primary : COLORS.textMuted,
              transition: 'all 0.15s',
              whiteSpace: 'nowrap',
              maxWidth: 220,
            }}>
              {resumeFile
                ? <><FileText size={14} strokeWidth={2} /><span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{resumeFile.name}</span></>
                : <><Upload size={14} strokeWidth={2} />Upload resume</>
              }
            </div>
          </label>
        </div>
      </header>

      {/* HERO */}
      <section style={{ padding: '80px 48px 48px', maxWidth: 1280, margin: '0 auto', textAlign: 'center' }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '6px 14px', background: COLORS.primaryLight,
          borderRadius: 100, marginBottom: 24,
          fontSize: 13, fontWeight: 500, color: COLORS.primaryDark,
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: COLORS.primary }}></span>
          H-1B intelligence for international students
        </div>
        <h2 style={{
          fontSize: 56, lineHeight: 1.1, fontWeight: 700,
          letterSpacing: '-0.03em', margin: '0 0 20px',
          maxWidth: 900, marginLeft: 'auto', marginRight: 'auto',
        }}>
          Find companies that{' '}
          <span style={{ color: COLORS.primary }}>actually sponsor</span>{' '}
          your visa.
        </h2>

      </section>

      {/* SEARCH BAR */}
      <section style={{ padding: '0 48px', maxWidth: 1280, margin: '0 auto' }}>
        <div style={{
          background: COLORS.surface,
          border: `1px solid ${COLORS.border}`,
          borderRadius: 16, padding: 8,
          display: 'flex', gap: 8,
          boxShadow: '0 1px 3px rgba(15, 23, 42, 0.04), 0 4px 24px rgba(59, 130, 246, 0.06)',
        }}>
          <div style={{ flex: 2, padding: '14px 20px', borderRadius: 10 }}>
            <label style={{ display: 'block', fontSize: 11, color: COLORS.textMuted, fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Role
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              style={{
                width: '100%', border: 'none', background: 'transparent',
                fontSize: 17, fontWeight: 600, color: COLORS.text,
                cursor: 'pointer', appearance: 'none', padding: 0,
              }}
            >
              {categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div style={{ width: 1, background: COLORS.border, margin: '12px 0' }}></div>
          <div style={{ flex: 1, padding: '14px 20px', borderRadius: 10 }}>
            <label style={{ display: 'block', fontSize: 11, color: COLORS.textMuted, fontWeight: 600, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              State
            </label>
            <select
              value={state}
              onChange={(e) => setState(e.target.value)}
              style={{
                width: '100%', border: 'none', background: 'transparent',
                fontSize: 17, fontWeight: 600, color: COLORS.text,
                cursor: 'pointer', appearance: 'none', padding: 0,
              }}
            >
              {states.map(s => <option key={s} value={s}>{s === 'All' ? 'Any state' : s}</option>)}
            </select>
          </div>
          <button
            onClick={fetchResults}
            className="search-btn"
            style={{
              background: COLORS.primary, color: 'white', border: 'none',
              padding: '0 32px', fontSize: 15, fontWeight: 600,
              cursor: 'pointer', borderRadius: 10,
              display: 'flex', alignItems: 'center', gap: 8,
              transition: 'background 0.15s',
            }}
          >
            {loading
              ? <Loader2 className="spin" size={17} strokeWidth={2.5} />
              : <Search size={17} strokeWidth={2.5} />} Search
          </button>
        </div>
      </section>

      {/* STATS */}
      <section style={{ padding: '48px 48px 24px', maxWidth: 1280, margin: '0 auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          {[
            { label: 'Companies sponsoring', value: stats.total_companies?.toLocaleString() || '0' },
            { label: 'Total LCA filings', value: stats.total_filings?.toLocaleString() || '0' },
            { label: 'Median salary', value: stats.median_salary ? formatSalary(stats.median_salary) : '—' },
            { label: 'New hires', value: `${stats.new_hire_pct || 0}%` },
          ].map((s, i) => (
            <div key={i} style={{
              padding: '20px 24px', background: COLORS.bgAlt,
              border: `1px solid ${COLORS.border}`, borderRadius: 12,
            }}>
              <div style={{ fontSize: 13, color: COLORS.textMuted, fontWeight: 500, marginBottom: 8 }}>
                {s.label}
              </div>
              <div style={{ fontSize: 32, fontWeight: 700, color: COLORS.text, letterSpacing: '-0.02em' }}>
                {s.value}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* RESULTS */}
      <section style={{ padding: '24px 48px 96px', maxWidth: 1280, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 20 }}>
          <div>
            <h3 style={{ fontSize: 24, fontWeight: 700, margin: 0, letterSpacing: '-0.02em' }}>
              {category === 'All' ? 'All roles' : category}
              <span style={{ color: COLORS.textMuted, fontWeight: 500 }}> · {state === 'All' ? 'all states' : state}</span>
            </h3>
            <p style={{ fontSize: 14, color: COLORS.textMuted, margin: '6px 0 0' }}>
              {loading ? 'Loading…' : `Showing ${Math.min(results.length, 25)} of ${searchData?.total || 0} companies`}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {[
              { id: 'count', label: 'Most sponsorships' },
              { id: 'salary', label: 'Highest pay' },
              { id: 'recent', label: 'Most recent' },
            ].map(s => (
              <button
                key={s.id}
                onClick={() => setSortBy(s.id)}
                className={`pill ${sortBy === s.id ? 'pill-active' : ''}`}
                style={{
                  background: 'white',
                  border: `1px solid ${COLORS.border}`,
                  color: COLORS.textMuted,
                  padding: '8px 16px', fontSize: 13, fontWeight: 500,
                  cursor: 'pointer', borderRadius: 8,
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div style={{
          background: COLORS.surface,
          border: `1px solid ${COLORS.border}`,
          borderRadius: 12, overflow: 'hidden',
          opacity: loading ? 0.5 : 1, transition: 'opacity 0.2s',
        }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: '60px 2fr 1fr 1.5fr 1.2fr 1fr 60px',
            padding: '14px 24px',
            background: COLORS.bgAlt,
            borderBottom: `1px solid ${COLORS.border}`,
            fontSize: 12, color: COLORS.textMuted, fontWeight: 600,
            textTransform: 'uppercase', letterSpacing: '0.05em',
          }}>
            <div>#</div>
            <div>Company</div>
            <div style={{ textAlign: 'right' }}>Sponsorships</div>
            <div>Salary (median)</div>
            <div>Locations</div>
            <div>Recent</div>
            <div></div>
          </div>

          {results.length === 0 && !loading ? (
            <div style={{ padding: 64, textAlign: 'center' }}>
              <p style={{ fontSize: 16, color: COLORS.textMuted, margin: 0 }}>
                No sponsoring employers found for this combination.
              </p>
            </div>
          ) : results.slice(0, 25).map((r, i, arr) => (
            <div
              key={r.employer}
              onClick={() => handleRowClick(r)}
              className="row-hover fade-row"
              style={{
                display: 'grid',
                gridTemplateColumns: '60px 2fr 1fr 1.5fr 1.2fr 1fr 60px',
                padding: '18px 24px',
                borderBottom: i < arr.length - 1 ? `1px solid ${COLORS.border}` : 'none',
                cursor: 'pointer', alignItems: 'center',
                animationDelay: `${i * 25}ms`,
              }}
            >
              <div style={{ fontSize: 13, color: COLORS.textLight, fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>
                {String(i + 1).padStart(2, '0')}
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, color: COLORS.text }}>
                {r.employer}
              </div>
              <div style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                <span style={{ fontSize: 18, fontWeight: 700, color: COLORS.primary }}>{r.count}</span>
                <span style={{ fontSize: 12, color: COLORS.textMuted, marginLeft: 6, fontWeight: 500 }}>filings</span>
              </div>
              <div>
                <div style={{ fontSize: 14, color: COLORS.text, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                  {formatSalary(r.median)}
                </div>
                <div style={{ fontSize: 12, color: COLORS.textMuted, marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
                  {formatSalary(r.min)} – {formatSalary(r.max)}
                </div>
              </div>
              <div style={{ fontSize: 13, color: COLORS.text }}>
                {r.city_list.slice(0, 2).join(', ')}
                {r.city_list.length > 2 && <span style={{ color: COLORS.textMuted }}> +{r.city_list.length - 2}</span>}
              </div>
              <div style={{ fontSize: 13, color: COLORS.textMuted, fontWeight: 500 }}>
                {r.months_ago === 0 ? 'this month' : `${r.months_ago}mo ago`}
              </div>
              <div style={{ textAlign: 'right' }}>
                <ArrowRight
                  className="arrow"
                  size={18}
                  strokeWidth={2}
                  style={{
                    color: COLORS.textLight, opacity: 0.4,
                    transform: 'translateX(-6px)', transition: 'all 0.15s',
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{
        borderTop: `1px solid ${COLORS.border}`,
        padding: '24px 48px',
        display: 'flex', justifyContent: 'space-between',
        fontSize: 13, color: COLORS.textMuted,
      }}>
        <span>Built from public DOL disclosure data. Not affiliated with USCIS or DOL.</span>
        <span>v0.1</span>
      </footer>

      {/* DETAIL PANEL */}
      {selectedCompany && (
        <div
          onClick={closeDetail}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(15, 23, 42, 0.4)',
            backdropFilter: 'blur(4px)',
            zIndex: 50,
            display: 'flex', justifyContent: 'flex-end',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="panel"
            style={{
              width: '50%', maxWidth: 720,
              background: COLORS.bg,
              height: '100vh', overflowY: 'auto',
            }}
          >
            <div style={{
              padding: '28px 36px',
              borderBottom: `1px solid ${COLORS.border}`,
              display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
              position: 'sticky', top: 0, background: COLORS.bg, zIndex: 1,
            }}>
              <div>
                <div style={{ fontSize: 12, color: COLORS.textMuted, fontWeight: 600, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Company profile
                </div>
                <h2 style={{ fontSize: 32, fontWeight: 700, margin: 0, letterSpacing: '-0.02em' }}>
                  {selectedCompany.employer}
                </h2>
              </div>
              <button
                onClick={closeDetail}
                className="close-btn"
                style={{
                  background: 'white',
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: 8, width: 36, height: 36,
                  cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'all 0.15s',
                }}
              >
                <X size={16} strokeWidth={2} color={COLORS.textMuted} />
              </button>
            </div>

            {detailLoading ? (
              <div style={{ padding: 80, textAlign: 'center' }}>
                <Loader2 className="spin" size={32} color={COLORS.primary} />
                <p style={{ marginTop: 16, color: COLORS.textMuted, fontSize: 14 }}>Loading company details…</p>
              </div>
            ) : companyDetail && (
              <div style={{ padding: '32px 36px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginBottom: 32 }}>
                  <div style={{
                    padding: 20, background: COLORS.primaryLighter,
                    border: `1px solid ${COLORS.primaryLight}`, borderRadius: 12,
                  }}>
                    <div style={{ fontSize: 12, color: COLORS.primaryDark, fontWeight: 600, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Total LCAs filed
                    </div>
                    <div style={{ fontSize: 40, fontWeight: 700, color: COLORS.primary, lineHeight: 1, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>
                      {companyDetail.count}
                    </div>
                    <div style={{ fontSize: 13, color: COLORS.textMuted, marginTop: 8 }}>
                      last 12 months · {category === 'All' ? 'all roles' : category}
                    </div>
                  </div>
                  <div style={{
                    padding: 20, background: COLORS.bgAlt,
                    border: `1px solid ${COLORS.border}`, borderRadius: 12,
                  }}>
                    <div style={{ fontSize: 12, color: COLORS.textMuted, fontWeight: 600, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Median salary
                    </div>
                    <div style={{ fontSize: 40, fontWeight: 700, color: COLORS.text, lineHeight: 1, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>
                      {formatSalary(companyDetail.median)}
                    </div>
                    <div style={{ fontSize: 13, color: COLORS.textMuted, marginTop: 8, fontVariantNumeric: 'tabular-nums' }}>
                      range {formatSalary(companyDetail.min)} – {formatSalary(companyDetail.max)}
                    </div>
                  </div>
                </div>

                {companyDetail.city_list?.length > 0 && (
                  <div style={{ marginBottom: 32 }}>
                    <h4 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 12px', color: COLORS.text }}>
                      Worksites
                    </h4>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {companyDetail.city_list.map(c => (
                        <span key={c} style={{
                          padding: '6px 12px', background: COLORS.bgAlt,
                          border: `1px solid ${COLORS.border}`,
                          fontSize: 13, color: COLORS.text,
                          borderRadius: 8, fontWeight: 500,
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                        }}>
                          <MapPin size={12} color={COLORS.primary} />
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {companyDetail.filings?.length > 0 && (
                  <div style={{ marginBottom: 32 }}>
                    <h4 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 12px', color: COLORS.text }}>
                      Recent filings
                    </h4>
                    <div style={{
                      background: COLORS.surface,
                      border: `1px solid ${COLORS.border}`,
                      borderRadius: 12, overflow: 'hidden',
                    }}>
                      {companyDetail.filings.map((f, i, arr) => (
                        <div
                          key={f.id}
                          style={{
                            padding: '14px 18px',
                            display: 'grid',
                            gridTemplateColumns: '2fr 1fr 80px 110px',
                            gap: 12, alignItems: 'center',
                            borderBottom: i < arr.length - 1 ? `1px solid ${COLORS.border}` : 'none',
                          }}
                        >
                          <div style={{ fontSize: 14, color: COLORS.text, fontWeight: 500 }}>
                            {f.title}
                          </div>
                          <div style={{ fontSize: 13, color: COLORS.textMuted }}>
                            {f.city}, {f.state}
                          </div>
                          <div style={{ fontSize: 14, color: COLORS.text, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                            {f.salary ? formatSalary(f.salary) : '—'}
                          </div>
                          <div style={{ fontSize: 12, color: COLORS.textMuted, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                            {formatDate(f.date)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{
                  padding: 20, background: COLORS.primaryLighter,
                  border: `1px solid ${COLORS.primaryLight}`, borderRadius: 12,
                }}>
                  <div style={{ fontSize: 12, color: COLORS.primaryDark, fontWeight: 600, marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    What this means
                  </div>
                  <p style={{ fontSize: 15, lineHeight: 1.6, margin: 0, color: COLORS.text }}>
                    <strong>{companyDetail.employer}</strong> filed{' '}
                    <strong style={{ color: COLORS.primary }}>{companyDetail.count} LCAs</strong> for {(category === 'All' ? 'roles' : category.toLowerCase() + 's')} in the last year, paying a median of{' '}
                    <strong>{formatSalary(companyDetail.median)}</strong>.
                    {companyDetail.count > 50 && ' This is a high-volume sponsor with established immigration infrastructure — your odds of sponsorship here are strong.'}
                    {companyDetail.count <= 50 && companyDetail.count > 10 && ' This company sponsors selectively but consistently. Worth applying to.'}
                    {companyDetail.count <= 10 && ' Lower-volume sponsor — sponsorship is likely role-by-role, but they\'ve done it before.'}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
