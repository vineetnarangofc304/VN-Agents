"""
Test suite for PDF Directory Extractor Agent (Agent 5)
Tests the /api/directory/* endpoints for extracting company data from PDFs
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://qikberry-whatsapp.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "vineetnarangofc@gmail.com"
TEST_PASSWORD = "InvoiceAgent@2024!"


@pytest.fixture(scope="module")
def auth_session():
    """Create authenticated session for all tests"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    return session


class TestDirectoryStats:
    """Test /api/directory/stats endpoint"""
    
    def test_stats_returns_extracted_true(self, auth_session):
        """GET /api/directory/stats should return extracted=true with 125 companies"""
        response = auth_session.get(f"{BASE_URL}/api/directory/stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total" in data, "Response should contain 'total' field"
        assert "extracted" in data, "Response should contain 'extracted' field"
        
        # Data should already be extracted (125 companies)
        assert data["extracted"] == True, f"Expected extracted=True, got {data['extracted']}"
        assert data["total"] == 125, f"Expected 125 companies, got {data['total']}"
        
        print(f"✓ Stats: {data['total']} companies extracted, batch_id: {data.get('batch_id', 'N/A')}")


class TestDirectoryCompanies:
    """Test /api/directory/companies endpoint"""
    
    def test_get_all_companies(self, auth_session):
        """GET /api/directory/companies should return 125 companies"""
        response = auth_session.get(f"{BASE_URL}/api/directory/companies")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "companies" in data, "Response should contain 'companies' array"
        assert "total" in data, "Response should contain 'total' field"
        
        companies = data["companies"]
        total = data["total"]
        
        assert total == 125, f"Expected 125 total companies, got {total}"
        assert len(companies) > 0, "Companies array should not be empty"
        
        # Verify company structure
        first_company = companies[0]
        required_fields = ["id", "name", "page_number"]
        for field in required_fields:
            assert field in first_company, f"Company should have '{field}' field"
        
        # Check optional fields exist
        optional_fields = ["address", "contact_person", "designation", "phone", "mobile", "email", "website", "profile"]
        for field in optional_fields:
            if field in first_company:
                print(f"  - {field}: present")
        
        print(f"✓ Retrieved {len(companies)} companies (total: {total})")
        print(f"  First company: {first_company.get('name', 'N/A')}")
    
    def test_search_benlycos(self, auth_session):
        """GET /api/directory/companies?search=benlycos should return filtered results"""
        response = auth_session.get(f"{BASE_URL}/api/directory/companies", params={"search": "benlycos"})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        companies = data.get("companies", [])
        
        # Should find at least one match
        print(f"✓ Search 'benlycos': found {len(companies)} results")
        
        if len(companies) > 0:
            for company in companies:
                print(f"  - {company.get('name', 'N/A')}")
    
    def test_search_4basecare(self, auth_session):
        """GET /api/directory/companies?search=4basecare should return matching results"""
        response = auth_session.get(f"{BASE_URL}/api/directory/companies", params={"search": "4basecare"})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        companies = data.get("companies", [])
        
        print(f"✓ Search '4basecare': found {len(companies)} results")
        
        if len(companies) > 0:
            for company in companies:
                print(f"  - {company.get('name', 'N/A')}")
    
    def test_search_by_email(self, auth_session):
        """Search should work with email addresses"""
        response = auth_session.get(f"{BASE_URL}/api/directory/companies", params={"search": "@gmail"})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        companies = data.get("companies", [])
        
        print(f"✓ Search '@gmail': found {len(companies)} results")
    
    def test_search_no_results(self, auth_session):
        """Search with non-existent term should return empty array"""
        response = auth_session.get(f"{BASE_URL}/api/directory/companies", params={"search": "xyznonexistent123"})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        companies = data.get("companies", [])
        
        assert len(companies) == 0, f"Expected 0 results for non-existent search, got {len(companies)}"
        print(f"✓ Search 'xyznonexistent123': correctly returned 0 results")


class TestDirectoryDownloadExcel:
    """Test /api/directory/download-excel endpoint"""
    
    def test_download_excel(self, auth_session):
        """GET /api/directory/download-excel should download an Excel file"""
        response = auth_session.get(f"{BASE_URL}/api/directory/download-excel")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheet" in content_type or "excel" in content_type.lower() or "octet-stream" in content_type, \
            f"Expected Excel content type, got {content_type}"
        
        # Check content disposition
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disposition, "Should have attachment disposition"
        assert ".xlsx" in content_disposition, "Filename should have .xlsx extension"
        
        # Check file size (should be > 0)
        content_length = len(response.content)
        assert content_length > 0, "Excel file should not be empty"
        
        print(f"✓ Excel download successful: {content_length} bytes")
        print(f"  Content-Disposition: {content_disposition}")
    
    def test_download_excel_with_search(self, auth_session):
        """GET /api/directory/download-excel?search=... should download filtered Excel"""
        response = auth_session.get(f"{BASE_URL}/api/directory/download-excel", params={"search": "tech"})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        content_length = len(response.content)
        assert content_length > 0, "Filtered Excel file should not be empty"
        
        print(f"✓ Filtered Excel download successful: {content_length} bytes")


class TestExistingAgentsStillWork:
    """Verify existing agents still work after adding PDF Extractor"""
    
    def test_invoices_endpoint(self, auth_session):
        """GET /api/invoices should still work"""
        response = auth_session.get(f"{BASE_URL}/api/invoices")
        
        assert response.status_code == 200, f"Invoices endpoint failed: {response.status_code}"
        
        data = response.json()
        assert "invoices" in data, "Should return invoices array"
        
        print(f"✓ Invoices endpoint working: {len(data['invoices'])} invoices")
    
    def test_refund_history_endpoint(self, auth_session):
        """GET /api/refund/history should still work"""
        response = auth_session.get(f"{BASE_URL}/api/refund/history")
        
        assert response.status_code == 200, f"Refund history endpoint failed: {response.status_code}"
        
        data = response.json()
        assert "history" in data, "Should return history array"
        
        print(f"✓ Refund history endpoint working: {len(data['history'])} entries")
    
    def test_stocks_portfolio_endpoint(self, auth_session):
        """GET /api/stocks/portfolio should still work"""
        response = auth_session.get(f"{BASE_URL}/api/stocks/portfolio")
        
        assert response.status_code == 200, f"Stocks portfolio endpoint failed: {response.status_code}"
        
        data = response.json()
        assert "portfolio" in data, "Should return portfolio array"
        
        print(f"✓ Stocks portfolio endpoint working: {len(data['portfolio'])} positions")
    
    def test_linkedin_companies_endpoint(self, auth_session):
        """GET /api/linkedin/companies should still work"""
        response = auth_session.get(f"{BASE_URL}/api/linkedin/companies")
        
        assert response.status_code == 200, f"LinkedIn companies endpoint failed: {response.status_code}"
        
        data = response.json()
        assert "companies" in data, "Should return companies array"
        
        print(f"✓ LinkedIn companies endpoint working: {len(data['companies'])} companies")
    
    def test_agents_list_includes_directory(self, auth_session):
        """GET /api/agents should include all 5 agents"""
        response = auth_session.get(f"{BASE_URL}/api/agents")
        
        assert response.status_code == 200, f"Agents endpoint failed: {response.status_code}"
        
        data = response.json()
        agents = data.get("agents", [])
        
        # Should have at least 4 agents (invoicing, refund, stocks, linkedin)
        assert len(agents) >= 4, f"Expected at least 4 agents, got {len(agents)}"
        
        agent_ids = [a["id"] for a in agents]
        print(f"✓ Agents list: {agent_ids}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
