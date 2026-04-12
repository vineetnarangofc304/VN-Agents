import { useState } from "react";
import axios from "axios";
import { FileText, CheckCircle, Loader2, RefreshCw, Mail, Copy, ExternalLink, Calendar } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const RefundAgent = () => {
  const [transactionInput, setTransactionInput] = useState("");
  const [refundRequest, setRefundRequest] = useState("");
  const [generatingRefund, setGeneratingRefund] = useState(false);

  const handleGenerate = async () => {
    if (!transactionInput.trim()) { alert("Please paste transaction details first"); return; }
    setGeneratingRefund(true);
    try {
      const response = await axios.post(`${API}/refund/generate`, { transaction_details: transactionInput });
      setRefundRequest(response.data.refund_request);
    } catch (err) {
      alert("Failed to generate refund request");
    } finally {
      setGeneratingRefund(false);
    }
  };

  return (
    <div className="refund-agent" data-testid="refund-agent">
      <header className="content-header">
        <div>
          <h1>Refund Agent</h1>
          <p>Generate compelling refund requests for failed Google Play transactions</p>
        </div>
      </header>

      <div className="gmail-section">
        <div className="gmail-status">
          <Mail size={24} />
          <div className="gmail-info">
            <span className="gmail-title">Gmail Connection</span>
            <span className="gmail-subtitle">Connect to auto-fetch Google Play receipts</span>
          </div>
          <button className="gmail-btn" onClick={() => alert("Gmail integration requires OAuth setup. Paste transaction details manually below.")} data-testid="gmail-connect-btn">
            <Mail size={16} /> Connect Gmail
          </button>
        </div>
      </div>

      <div className="transaction-input-section">
        <h2><FileText size={20} /> Paste Transaction Details</h2>
        <p className="section-desc">Copy transaction details from Google Play and paste below</p>
        <textarea
          className="transaction-textarea"
          placeholder={"Paste transaction details here...\n\nExample:\nOrder ID: GPA.1234-5678-9012\nDate: March 30, 2026\nItem: Game Currency Pack\nAmount: ₹990.00\nWhat went wrong: Payment was charged but items were never received"}
          value={transactionInput}
          onChange={(e) => setTransactionInput(e.target.value)}
          data-testid="transaction-input"
        />
        <button className="generate-btn" onClick={handleGenerate} disabled={generatingRefund || !transactionInput.trim()} data-testid="generate-refund-btn">
          {generatingRefund ? <><Loader2 className="spin" size={18} /> Generating...</> : <><RefreshCw size={18} /> Generate Refund Request</>}
        </button>
      </div>

      {refundRequest && (
        <div className="refund-output-section">
          <h2><CheckCircle size={20} /> Your Refund Request</h2>
          <div className="refund-output"><pre>{refundRequest}</pre></div>
          <div className="refund-actions">
            <button className="action-btn copy" onClick={() => { navigator.clipboard.writeText(refundRequest); alert("Copied!"); }} data-testid="copy-refund-btn">
              <Copy size={16} /> Copy to Clipboard
            </button>
            <a href="https://play.google.com/store/account/orderhistory" target="_blank" rel="noopener noreferrer" className="action-btn submit-link" data-testid="submit-refund-link">
              <ExternalLink size={16} /> Open Google Play Refunds
            </a>
          </div>
        </div>
      )}
    </div>
  );
};

export default RefundAgent;
