import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Receipt, RefreshCw, TrendingUp, Linkedin, BookOpen, ShieldCheck, Radar } from "lucide-react";

import LandingPage from "./components/LandingPage";
import AgentLogin from "./components/AgentLogin";
import InvoicingAgent from "./components/InvoicingAgent";
import RefundAgent from "./components/RefundAgent";
import StockAgent from "./components/StockAgent";
import LinkedInAgent from "./components/LinkedInAgent";
import DirectoryAgent from "./components/DirectoryAgent";
import AccountChecker from "./components/AccountChecker";
import CatchmentMining from "./components/CatchmentMining";

import "./App.css";

const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />

        <Route path="/invoicing" element={
          <AgentLogin agentName="Invoicing Agent" agentIcon={Receipt} agentColor="#3b82f6">
            <InvoicingAgent />
          </AgentLogin>
        } />

        <Route path="/refund" element={
          <AgentLogin agentName="Refund Agent" agentIcon={RefreshCw} agentColor="#f59e0b">
            <RefundAgent />
          </AgentLogin>
        } />

        <Route path="/stocks" element={
          <AgentLogin agentName="Stock Investor" agentIcon={TrendingUp} agentColor="#16a34a">
            <StockAgent />
          </AgentLogin>
        } />

        <Route path="/linkedin" element={
          <AgentLogin agentName="LinkedIn Agent" agentIcon={Linkedin} agentColor="#0a66c2">
            <LinkedInAgent />
          </AgentLogin>
        } />

        <Route path="/directory" element={
          <AgentLogin agentName="PDF Extractor" agentIcon={BookOpen} agentColor="#8b5cf6">
            <DirectoryAgent />
          </AgentLogin>
        } />

        <Route path="/checker" element={
          <AgentLogin agentName="Account Checker" agentIcon={ShieldCheck} agentColor="#ef4444">
            <AccountChecker />
          </AgentLogin>
        } />

        <Route path="/catchment" element={
          <AgentLogin agentName="Catchment Mining" agentIcon={Radar} agentColor="#14b8a6">
            <CatchmentMining />
          </AgentLogin>
        } />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
