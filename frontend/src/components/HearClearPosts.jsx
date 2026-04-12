import { useState, useEffect } from "react";
import { Copy, CheckCircle, Download, Loader2, Image, RefreshCw, ChevronLeft, ChevronRight, Sparkles } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BASE = process.env.REACT_APP_BACKEND_URL;

const HearClearPosts = () => {
  const [copied, setCopied] = useState(false);
  const [variations, setVariations] = useState([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [themes, setThemes] = useState([]);
  const [selectedTheme, setSelectedTheme] = useState(null);

  // Load saved infographics + themes on mount
  useEffect(() => {
    const init = async () => {
      try {
        const [infRes, themeRes] = await Promise.all([
          fetch(`${API}/linkedin/infographics`),
          fetch(`${API}/linkedin/infographic-themes`)
        ]);
        if (infRes.ok) {
          const data = await infRes.json();
          const saved = (data.infographics || []).map(item => ({
            imageUrl: `${BASE}${item.url}`,
            downloadUrl: `${BASE}${item.download_url}`,
            filename: item.filename,
            theme: null,
            postContent: null
          }));
          if (saved.length > 0) {
            setVariations(saved);
            setCurrentIdx(0);
          }
        }
        if (themeRes.ok) {
          const data = await themeRes.json();
          setThemes(data.themes || []);
        }
      } catch (err) {
        console.error("Failed to load:", err);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const currentItem = variations[currentIdx] || null;

  const handleCopy = () => {
    const text = currentItem?.postContent || "Visit hearclearindia.com";
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleGenerateVariation = async () => {
    setGenerating(true);
    setError(null);
    try {
      // Start background generation
      const startUrl = selectedTheme !== null
        ? `${API}/linkedin/generate-hearclear-infographic?theme_id=${selectedTheme}`
        : `${API}/linkedin/generate-hearclear-infographic`;
      const startRes = await fetch(startUrl, { method: "POST" });
      if (!startRes.ok) {
        const errData = await startRes.json().catch(() => ({}));
        throw new Error(errData.detail || `Start failed (${startRes.status})`);
      }
      const startData = await startRes.json();
      const jobId = startData.job_id;

      // Poll for completion
      let attempts = 0;
      const maxAttempts = 40; // ~2 minutes
      while (attempts < maxAttempts) {
        await new Promise(r => setTimeout(r, 3000));
        attempts++;
        try {
          const pollRes = await fetch(`${API}/linkedin/generate-status/${jobId}`);
          if (!pollRes.ok) continue;
          const pollData = await pollRes.json();

          if (pollData.status === "completed") {
            const newItem = {
              imageUrl: `${BASE}${pollData.image_url}`,
              downloadUrl: `${BASE}${pollData.download_url}`,
              filename: pollData.filename,
              theme: pollData.theme || null,
              postContent: pollData.post_content || null
            };
            setVariations(prev => {
              const updated = [newItem, ...prev];
              setCurrentIdx(0);
              return updated;
            });
            setGenerating(false);
            return;
          } else if (pollData.status === "failed") {
            throw new Error(pollData.error || "Generation failed");
          }
        } catch (pollErr) {
          if (pollErr.message && !pollErr.message.includes("Generation failed")) continue;
          throw pollErr;
        }
      }
      throw new Error("Generation timed out — please try again");
    } catch (err) {
      setError(err.message || "Failed to generate infographic");
    } finally {
      setGenerating(false);
    }
  };

  const handleDownloadImage = async () => {
    if (!currentItem) return;
    try {
      // Use the image URL directly (not download URL) to avoid any routing issues
      const imageUrl = currentItem.downloadUrl || currentItem.imageUrl;
      const response = await fetch(imageUrl);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = currentItem.filename || "HearClear_Infographic.png";
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      // Cleanup after a short delay
      setTimeout(() => {
        document.body.removeChild(link);
        window.URL.revokeObjectURL(blobUrl);
      }, 200);
    } catch (err) {
      console.error("Download failed, trying fallback:", err);
      // Fallback: open image URL in new tab for manual save
      window.open(currentItem.imageUrl, "_blank");
    }
  };

  const hasVariations = variations.length > 0;

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
        <h2>HearClear India — Strategic Content</h2>
        <span className="hc-subtitle">Each infographic tells a different story — market, AI, ecosystem, investors, patients</span>
      </div>

      {/* Theme Selector */}
      <div className="hc-theme-selector" data-testid="theme-selector">
        <div className="hc-theme-label">
          <Sparkles size={16} /> Choose a theme or let AI pick:
        </div>
        <div className="hc-theme-chips">
          <button
            className={`hc-theme-chip ${selectedTheme === null ? "active" : ""}`}
            onClick={() => setSelectedTheme(null)}
            data-testid="theme-random"
          >
            Random
          </button>
          {themes.map(t => (
            <button
              key={t.id}
              className={`hc-theme-chip ${selectedTheme === t.id ? "active" : ""}`}
              onClick={() => setSelectedTheme(t.id)}
              title={t.subtitle}
              data-testid={`theme-${t.slug}`}
            >
              {t.title}
            </button>
          ))}
        </div>
      </div>

      {/* Generate Button (always visible) */}
      <div className="hc-generate-bar">
        <button
          className="hc-generate-btn"
          onClick={handleGenerateVariation}
          disabled={generating}
          data-testid="generate-infographic-btn"
        >
          {generating ? (
            <><Loader2 size={16} className="spin" /> Generating new infographic...</>
          ) : (
            <><Image size={16} /> Generate {selectedTheme !== null && themes[selectedTheme] ? `"${themes[selectedTheme].title}"` : "Random Theme"} Infographic</>
          )}
        </button>
        {error && <div className="hc-error" data-testid="infographic-error">{error}</div>}
      </div>

      {/* Current theme badge */}
      {currentItem?.theme && (
        <div className="hc-post-theme">{currentItem.theme}</div>
      )}

      {hasVariations && (
        <div className="hc-post-layout">
          {/* Infographic Area */}
          <div className="hc-infographic-container">
            <img
              key={currentItem.imageUrl}
              src={currentItem.imageUrl}
              alt={`HearClear Infographic ${currentIdx + 1}`}
              className="hc-infographic"
              data-testid="infographic-image"
            />
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
                  {currentIdx + 1} of {variations.length}
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
            </div>
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
          </div>

          {/* Post Content */}
          <div className="hc-post-content-area">
            <div className="hc-post-text" data-testid="post-content">
              {currentItem?.postContent || "Generate a themed infographic to see the matching LinkedIn post here."}
            </div>
            <div className="hc-post-actions">
              {currentItem?.postContent && (
                <button
                  className={`hc-copy-btn ${copied ? "copied" : ""}`}
                  onClick={handleCopy}
                  data-testid="copy-post-btn"
                >
                  {copied ? <><CheckCircle size={14} /> Copied!</> : <><Copy size={14} /> Copy Post</>}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {!hasVariations && !generating && (
        <div className="hc-empty-state">
          <Image size={48} />
          <p>Select a theme above and generate your first infographic</p>
        </div>
      )}
    </div>
  );
};

export default HearClearPosts;
