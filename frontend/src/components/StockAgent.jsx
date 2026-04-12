import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Loader2, RefreshCw, Search, TrendingUp, Bell, DollarSign, Target, Plus, Trash2, X, ArrowUp, ArrowDown } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const StockAgent = () => {
  const [stocks, setStocks] = useState([]);
  const [stockAlerts, setStockAlerts] = useState([]);
  const [portfolio, setPortfolio] = useState([]);
  const [loadingStocks, setLoadingStocks] = useState(false);
  const [stockDetails, setStockDetails] = useState(null);
  const [showAddPosition, setShowAddPosition] = useState(false);
  const [newPosition, setNewPosition] = useState({ symbol: "", buy_price: "", quantity: "", target_pct: "30" });

  const fetchStocks = useCallback(async () => {
    setLoadingStocks(true);
    try {
      const response = await axios.get(`${API}/stocks/scanner`);
      setStocks(response.data.stocks || []);
    } catch (err) {
      console.error("Error fetching stocks:", err);
    } finally {
      setLoadingStocks(false);
    }
  }, []);

  const fetchPortfolio = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/stocks/portfolio`);
      setPortfolio(response.data.portfolio || []);
      setStockAlerts(response.data.alerts || []);
    } catch (err) {
      console.error("Error fetching portfolio:", err);
    }
  }, []);

  const fetchStockDetails = async (symbol) => {
    try {
      const response = await axios.get(`${API}/stocks/${symbol}/details`);
      setStockDetails(response.data);
    } catch (err) {
      alert("Failed to fetch stock details");
    }
  };

  const addToPortfolio = async () => {
    if (!newPosition.symbol || !newPosition.buy_price || !newPosition.quantity) { alert("Please fill all fields"); return; }
    try {
      await axios.post(`${API}/stocks/portfolio/add`, {
        symbol: newPosition.symbol, buy_price: parseFloat(newPosition.buy_price),
        quantity: parseInt(newPosition.quantity), target_pct: parseFloat(newPosition.target_pct)
      });
      setNewPosition({ symbol: "", buy_price: "", quantity: "", target_pct: "30" });
      setShowAddPosition(false);
      fetchPortfolio();
    } catch (err) { alert("Failed to add position"); }
  };

  const sellPosition = async (entryId, currentPrice) => {
    const sellPrice = prompt("Enter sell price:", currentPrice);
    if (!sellPrice) return;
    try { await axios.post(`${API}/stocks/portfolio/${entryId}/sell?sell_price=${parseFloat(sellPrice)}`); fetchPortfolio(); }
    catch (err) { alert("Failed to sell position"); }
  };

  const deletePosition = async (entryId) => {
    if (!window.confirm("Delete this position?")) return;
    try { await axios.delete(`${API}/stocks/portfolio/${entryId}`); fetchPortfolio(); }
    catch (err) { alert("Failed to delete"); }
  };

  useEffect(() => { fetchStocks(); fetchPortfolio(); }, [fetchStocks, fetchPortfolio]);

  return (
    <div className="stock-agent" data-testid="stock-agent">
      <header className="content-header">
        <div>
          <h1>Stock Investor Agent</h1>
          <p>Track high-volume undervalued NSE stocks with buy/sell alerts</p>
        </div>
        <button className="refresh-btn" onClick={() => { fetchStocks(); fetchPortfolio(); }} disabled={loadingStocks}>
          <RefreshCw size={18} className={loadingStocks ? "spin" : ""} /> Refresh Data
        </button>
      </header>

      {stockAlerts.length > 0 && (
        <div className="alerts-section">
          <h2><Bell size={20} /> Active Alerts</h2>
          {stockAlerts.map((alert, idx) => (
            <div key={idx} className={`alert-card ${alert.type}`}><Target size={20} /><span>{alert.message}</span></div>
          ))}
        </div>
      )}

      <div className="portfolio-section">
        <div className="section-header">
          <h2><DollarSign size={20} /> Your Portfolio</h2>
          <button className="add-btn" onClick={() => setShowAddPosition(true)}><Plus size={16} /> Add Position</button>
        </div>
        {showAddPosition && (
          <div className="add-position-form">
            <input placeholder="Symbol (e.g., RELIANCE)" value={newPosition.symbol} onChange={(e) => setNewPosition({...newPosition, symbol: e.target.value.toUpperCase()})} />
            <input placeholder="Buy Price" type="number" value={newPosition.buy_price} onChange={(e) => setNewPosition({...newPosition, buy_price: e.target.value})} />
            <input placeholder="Quantity" type="number" value={newPosition.quantity} onChange={(e) => setNewPosition({...newPosition, quantity: e.target.value})} />
            <input placeholder="Target %" type="number" value={newPosition.target_pct} onChange={(e) => setNewPosition({...newPosition, target_pct: e.target.value})} />
            <button className="save-btn" onClick={addToPortfolio}>Add</button>
            <button className="cancel-btn" onClick={() => setShowAddPosition(false)}>Cancel</button>
          </div>
        )}
        {portfolio.length === 0 ? (
          <div className="empty-portfolio"><DollarSign size={48} /><p>No positions yet. Add stocks to track.</p></div>
        ) : (
          <div className="portfolio-list">
            {portfolio.filter(p => p.status === "holding").map((pos) => (
              <div key={pos.id} className="portfolio-card">
                <div className="portfolio-info">
                  <span className="portfolio-symbol">{pos.symbol}</span>
                  <span className="portfolio-qty">{pos.quantity} shares</span>
                </div>
                <div className="portfolio-prices">
                  <div className="price-row"><span className="label">Buy:</span><span>₹{pos.buy_price}</span></div>
                  <div className="price-row"><span className="label">Current:</span><span>₹{pos.current_price || "..."}</span></div>
                  <div className="price-row"><span className="label">Target:</span><span>₹{pos.target_price}</span></div>
                </div>
                <div className={`portfolio-pnl ${(pos.profit_loss_pct || 0) >= 0 ? "profit" : "loss"}`}>
                  {(pos.profit_loss_pct || 0) >= 0 ? <ArrowUp size={16} /> : <ArrowDown size={16} />}
                  {pos.profit_loss_pct?.toFixed(1) || 0}%
                </div>
                <div className="portfolio-actions">
                  <button className="sell-btn" onClick={() => sellPosition(pos.id, pos.current_price)}>Sell</button>
                  <button className="delete-btn" onClick={() => deletePosition(pos.id)}><Trash2 size={14} /></button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="scanner-section">
        <h2><Search size={20} /> Top Volume Movers (Under ₹100)</h2>
        <p className="criteria-info">NSE stocks under ₹100 sorted by shares traded today | Top 50 | Highlights: Price &lt; 60% of 52W high</p>
        {loadingStocks ? (
          <div className="loading-state"><Loader2 className="spin" size={32} /><span>Scanning stocks...</span></div>
        ) : (
          <div className="stock-list">
            <div className="stock-header"><span>Symbol</span><span>Price</span><span>Today's Volume</span><span>7D Avg Vol</span><span>% of 52W</span><span>Status</span></div>
            {stocks.map((stock) => (
              <div key={stock.symbol} className={`stock-row ${stock.meets_criteria ? "highlight" : ""}`} onClick={() => fetchStockDetails(stock.symbol)}>
                <span className="stock-symbol">{stock.symbol}</span>
                <span>₹{stock.current_price}</span>
                <span className={stock.high_volume_day ? "high-volume" : ""}>{stock.today_volume_formatted}</span>
                <span>{stock.avg_volume_7d_formatted}</span>
                <span className={stock.price_vs_52w_pct < 60 ? "undervalued" : ""}>{stock.price_vs_52w_pct}%</span>
                <span>
                  {stock.meets_criteria && stock.high_volume_day && <span className="buy-signal">BUY SIGNAL</span>}
                  {stock.high_volume_day && !stock.meets_criteria && <span className="watch">HIGH VOL</span>}
                  {stock.meets_criteria && !stock.high_volume_day && <span className="undervalued-tag">UNDERVALUED</span>}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {stockDetails && (
        <div className="stock-modal" onClick={() => setStockDetails(null)}>
          <div className="stock-modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="close-modal" onClick={() => setStockDetails(null)}><X size={20} /></button>
            <h2>{stockDetails.symbol} - {stockDetails.name}</h2>
            <div className="stock-detail-grid">
              <div className="detail-item"><span className="label">Current Price</span><span className="value">₹{stockDetails.current_price}</span></div>
              <div className="detail-item"><span className="label">52W High</span><span className="value">₹{stockDetails.week_52_high}</span></div>
              <div className="detail-item"><span className="label">52W Low</span><span className="value">₹{stockDetails.week_52_low}</span></div>
              <div className="detail-item"><span className="label">% of 52W High</span><span className="value">{stockDetails.price_vs_52w_pct}%</span></div>
              <div className="detail-item"><span className="label">Sector</span><span className="value">{stockDetails.sector}</span></div>
              <div className="detail-item"><span className="label">P/E Ratio</span><span className="value">{stockDetails.pe_ratio?.toFixed(2) || "N/A"}</span></div>
            </div>
            <h3>Recent News</h3>
            <div className="news-list">
              {stockDetails.news?.length > 0 ? stockDetails.news.map((n, i) => (
                <a key={i} href={n.link} target="_blank" rel="noopener noreferrer" className="news-item">
                  <span className="news-title">{n.title}</span><span className="news-date">{n.date}</span>
                </a>
              )) : <p>No recent news found</p>}
            </div>
            <button className="add-to-portfolio-btn" onClick={() => {
              setNewPosition({...newPosition, symbol: stockDetails.symbol, buy_price: stockDetails.current_price.toString()});
              setShowAddPosition(true); setStockDetails(null);
            }}><Plus size={16} /> Add to Portfolio</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default StockAgent;
