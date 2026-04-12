import { useState, useEffect } from "react";
import { Copy, CheckCircle, Download, Loader2, Image, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BASE = process.env.REACT_APP_BACKEND_URL;

const UNIFIED_POST = `We're standing at the intersection of healthcare's biggest blind spot and India's largest untapped opportunity.

63 million Indians live with disabling hearing loss. Only 5-7% use hearing aids — compared to 30% in developed nations. Over 90% of this market is fragmented mom-and-pop shops with zero clinical standards.

HearClear is building India's largest organized hearing care network. Here's what makes us different:

THE VISION — 40+ clinics across North India today. Target: 500-600 clinics. We're not selling hearing aids — we're building a comprehensive hearing care institution at scale.

AI-POWERED DIAGNOSTICS — Our proprietary AI test delivers 98% clinical-grade accuracy in just 8-10 minutes, replacing the traditional 45-minute soundproof booth test. We screen 10x more patients daily and catch hearing loss earlier than anyone else.

ECOSYSTEM INTEGRATION — Narayana Health, MAX@Home, EMOHA, 2050 Healthcare, and Healthians already partner with us. We embed into their operations as their audiology department — creating powerful referral loops.

CLINICAL DEPTH — With 100+ audiologists (India's largest private team), full-spectrum diagnostics (PTA, Impedance, OAE, BERA), cochlear implant referrals, speech therapy, and tinnitus management — we're a clinical powerhouse, not a retail shop.

THE OPPORTUNITY — India's hearing care market is $2B+, growing 15% YoY. WHO has proven the direct link between hearing loss and 5x higher dementia risk. India's aging population makes this urgent.

JOIN US — Whether you're an ENT specialist, hospital CEO, audiologist, healthcare partner, or investor — let's build India's hearing care revolution together.

DM me or comment below. Let's build this together.

#HearingCareRevolution #HealthcareTransformation #India2030 #InvestInHealth #HearClearGrowth #AIInHealthCare #ClinicalExcellence`;

const HearClearPosts = () => {
  const [copied, setCopied] = useState(false);
  const [variations, setVariations] = useState([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load saved infographics on mount
  useEffect(() => {
    const loadSaved = async () => {
      try {
        const res = await fetch(`${API}/linkedin/infographics`);
        if (res.ok) {
          const data = await res.json();
          const saved = (data.infographics || []).map(item => ({
            imageUrl: `${BASE}${item.url}`,
            downloadUrl: `${BASE}${item.download_url}`,
            filename: item.filename
          }));
          if (saved.length > 0) {
            setVariations(saved);
            setCurrentIdx(0);
          }
        }
      } catch (err) {
        console.error("Failed to load saved infographics:", err);
      } finally {
        setLoading(false);
      }
    };
    loadSaved();
  }, []);

  const handleCopy = () => {
    navigator.clipboard.writeText(UNIFIED_POST);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleGenerateVariation = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${API}/linkedin/generate-hearclear-infographic`, { method: "POST" });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Generation failed (${res.status})`);
      }
      const data = await res.json();
      const newItem = {
        imageUrl: `${BASE}${data.image_url}`,
        downloadUrl: `${BASE}${data.image_url.replace('/infographic/', '/infographic-download/')}`,
        filename: data.image_url.split('/').pop()
      };
      setVariations(prev => {
        const updated = [newItem, ...prev];
        setCurrentIdx(0);
        return updated;
      });
    } catch (err) {
      setError(err.message || "Failed to generate infographic");
    } finally {
      setGenerating(false);
    }
  };

  const handleDownloadImage = () => {
    const current = variations[currentIdx];
    if (!current) return;
    // Use the dedicated download endpoint which sets Content-Disposition: attachment
    window.open(current.downloadUrl, "_blank");
  };

  const hasVariations = variations.length > 0;
  const currentImage = hasVariations ? variations[currentIdx] : null;

  if (loading) {
    return (
      <div className="hc-posts" data-testid="hearclear-posts">
        <div style={{ display: "flex", justifyContent: "center", padding: "60px 0", color: "var(--text-muted)" }}>
          <Loader2 size={32} className="spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="hc-posts" data-testid="hearclear-posts">
      <div className="hc-posts-header">
        <h2>HearClear India — Corporate One-Pager</h2>
        <span className="hc-subtitle">McKinsey-standard unified infographic & LinkedIn post</span>
      </div>

      <div className="hc-post-theme">UNIFIED CORPORATE POST</div>
      <h3 className="hc-post-title">Building India's Largest Organized Hearing Care Network</h3>

      <div className="hc-post-layout">
        {/* Infographic Area */}
        <div className="hc-infographic-container">
          {hasVariations ? (
            <>
              <img
                key={currentImage.imageUrl}
                src={currentImage.imageUrl}
                alt={`HearClear Infographic — Variation ${currentIdx + 1}`}
                className="hc-infographic"
                data-testid="infographic-image"
              />
              {/* Navigation for multiple variations */}
              {variations.length > 1 && (
                <div className="hc-variation-nav" data-testid="variation-nav">
                  <button
                    className="hc-nav-arrow"
                    disabled={currentIdx === 0}
                    onClick={() => setCurrentIdx(currentIdx - 1)}
                    data-testid="prev-variation-btn"
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <span className="hc-variation-label">
                    Variation {currentIdx + 1} of {variations.length}
                  </span>
                  <button
                    className="hc-nav-arrow"
                    disabled={currentIdx === variations.length - 1}
                    onClick={() => setCurrentIdx(currentIdx + 1)}
                    data-testid="next-variation-btn"
                  >
                    <ChevronRight size={18} />
                  </button>
                </div>
              )}
              <div className="hc-infographic-actions">
                <button className="hc-download-img-btn" onClick={handleDownloadImage} data-testid="download-infographic-btn">
                  <Download size={14} /> Download
                </button>
                <button
                  className="hc-regenerate-btn"
                  onClick={handleGenerateVariation}
                  disabled={generating}
                  data-testid="regenerate-infographic-btn"
                >
                  {generating ? (
                    <><Loader2 size={14} className="spin" /> Generating...</>
                  ) : (
                    <><RefreshCw size={14} /> New Variation</>
                  )}
                </button>
              </div>
              {/* Thumbnail strip */}
              {variations.length > 1 && (
                <div className="hc-thumbnail-strip" data-testid="thumbnail-strip">
                  {variations.map((item, idx) => (
                    <button
                      key={item.filename}
                      className={`hc-thumb ${idx === currentIdx ? "active" : ""}`}
                      onClick={() => setCurrentIdx(idx)}
                      data-testid={`thumb-${idx}`}
                    >
                      <img src={item.imageUrl} alt={`v${idx + 1}`} />
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="hc-infographic-placeholder" data-testid="infographic-placeholder">
              {generating ? (
                <div className="hc-generating">
                  <Loader2 size={40} className="spin" />
                  <p>Generating Blue & Gold infographic...</p>
                  <span>This may take 15-30 seconds</span>
                </div>
              ) : (
                <>
                  <Image size={48} />
                  <p>Generate your corporate infographic</p>
                  <span>Blue & Gold | McKinsey Standard | One-Pager</span>
                  {error && <div className="hc-error" data-testid="infographic-error">{error}</div>}
                  <button
                    className="hc-generate-btn"
                    onClick={handleGenerateVariation}
                    data-testid="generate-infographic-btn"
                  >
                    <Image size={16} /> Generate Infographic
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {/* Post Content */}
        <div className="hc-post-content-area">
          <div className="hc-post-text" data-testid="post-content">
            {UNIFIED_POST}
          </div>
          <div className="hc-post-actions">
            <button
              className={`hc-copy-btn ${copied ? "copied" : ""}`}
              onClick={handleCopy}
              data-testid="copy-post-btn"
            >
              {copied ? <><CheckCircle size={14} /> Copied!</> : <><Copy size={14} /> Copy Post</>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HearClearPosts;
