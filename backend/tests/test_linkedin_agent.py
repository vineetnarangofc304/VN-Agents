"""
LinkedIn Agent API Tests
Tests for LinkedIn Agent endpoints including:
- Companies listing
- Accounts management
- OAuth auth URL generation
- Content generation
- Post history
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "vineetnarangofc@gmail.com"
TEST_PASSWORD = "InvoiceAgent@2024!"


class TestLinkedInAgentAPIs:
    """LinkedIn Agent API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth cookies
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if login_response.status_code != 200:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
        
        yield
        
        # Logout after tests
        self.session.post(f"{BASE_URL}/api/auth/logout")
    
    # ============== Companies API Tests ==============
    def test_get_companies_returns_three_companies(self):
        """GET /api/linkedin/companies returns 3 companies (fundle, hearclear, tagnpay)"""
        response = self.session.get(f"{BASE_URL}/api/linkedin/companies")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "companies" in data, "Response should contain 'companies' key"
        
        companies = data["companies"]
        assert len(companies) == 3, f"Expected 3 companies, got {len(companies)}"
        
        # Verify company IDs
        company_ids = [c["id"] for c in companies]
        assert "fundle" in company_ids, "fundle company should be present"
        assert "hearclear" in company_ids, "hearclear company should be present"
        assert "tagnpay" in company_ids, "tagnpay company should be present"
        
        # Verify company structure
        for company in companies:
            assert "id" in company, "Company should have 'id'"
            assert "name" in company, "Company should have 'name'"
            assert "tagline" in company, "Company should have 'tagline'"
            assert "description" in company, "Company should have 'description'"
            assert "website" in company, "Company should have 'website'"
        
        print(f"✓ Companies API returned {len(companies)} companies: {company_ids}")
    
    # ============== Accounts API Tests ==============
    def test_get_accounts_returns_array(self):
        """GET /api/linkedin/accounts returns accounts array (empty initially)"""
        response = self.session.get(f"{BASE_URL}/api/linkedin/accounts")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "accounts" in data, "Response should contain 'accounts' key"
        assert isinstance(data["accounts"], list), "accounts should be a list"
        
        print(f"✓ Accounts API returned {len(data['accounts'])} accounts")
    
    # ============== OAuth Auth URL Tests ==============
    def test_get_auth_url_returns_valid_url(self):
        """GET /api/linkedin/auth returns auth_url with correct client_id and scopes"""
        response = self.session.get(f"{BASE_URL}/api/linkedin/auth")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "auth_url" in data, "Response should contain 'auth_url'"
        assert "state" in data, "Response should contain 'state' for CSRF protection"
        
        auth_url = data["auth_url"]
        
        # Verify URL structure
        assert "linkedin.com/oauth/v2/authorization" in auth_url, "Should be LinkedIn OAuth URL"
        assert "client_id=" in auth_url, "Should contain client_id"
        assert "scope=" in auth_url, "Should contain scope"
        assert "state=" in auth_url, "Should contain state"
        assert "redirect_uri=" in auth_url, "Should contain redirect_uri"
        
        # Verify scopes include required permissions
        assert "openid" in auth_url or "profile" in auth_url, "Should include profile scope"
        assert "w_member_social" in auth_url, "Should include w_member_social scope for posting"
        
        print(f"✓ Auth URL generated successfully with state: {data['state'][:20]}...")
    
    # ============== Content Generation Tests ==============
    def test_generate_content_for_fundle(self):
        """POST /api/linkedin/generate-content with company=fundle generates posts"""
        response = self.session.post(
            f"{BASE_URL}/api/linkedin/generate-content",
            json={
                "company": "fundle",
                "topic": "retail data intelligence",
                "tone": "professional",
                "post_count": 1
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "posts" in data, "Response should contain 'posts'"
        
        posts = data["posts"]
        assert len(posts) >= 1, "Should generate at least 1 post"
        
        # Verify post structure
        post = posts[0]
        assert "content" in post, "Post should have 'content'"
        assert "company" in post, "Post should have 'company'"
        assert "generated_at" in post, "Post should have 'generated_at'"
        
        # Verify content is not empty and not an error
        assert len(post["content"]) > 50, "Generated content should be substantial"
        assert "error" not in post or not post.get("error"), "Post should not have error"
        
        print(f"✓ Generated content for fundle ({len(post['content'])} chars)")
    
    def test_generate_content_invalid_company(self):
        """POST /api/linkedin/generate-content with invalid company returns 400"""
        response = self.session.post(
            f"{BASE_URL}/api/linkedin/generate-content",
            json={
                "company": "invalid_company",
                "post_count": 1
            }
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid company, got {response.status_code}"
        print("✓ Invalid company correctly returns 400")
    
    # ============== Post History Tests ==============
    def test_get_post_history_returns_array(self):
        """GET /api/linkedin/posts returns posts array (empty initially)"""
        response = self.session.get(f"{BASE_URL}/api/linkedin/posts")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "posts" in data, "Response should contain 'posts'"
        assert isinstance(data["posts"], list), "posts should be a list"
        
        print(f"✓ Post history API returned {len(data['posts'])} posts")
    
    def test_get_post_history_with_company_filter(self):
        """GET /api/linkedin/posts with company filter works"""
        response = self.session.get(f"{BASE_URL}/api/linkedin/posts?company=fundle")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "posts" in data, "Response should contain 'posts'"
        
        # If there are posts, verify they're all for fundle
        for post in data["posts"]:
            assert post.get("company") == "fundle", "Filtered posts should be for fundle"
        
        print(f"✓ Post history with company filter returned {len(data['posts'])} posts")
    
    # ============== Schedule API Tests ==============
    def test_get_schedule_status(self):
        """GET /api/linkedin/schedule/status returns schedules array"""
        response = self.session.get(f"{BASE_URL}/api/linkedin/schedule/status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "schedules" in data, "Response should contain 'schedules'"
        assert isinstance(data["schedules"], list), "schedules should be a list"
        
        print(f"✓ Schedule status API returned {len(data['schedules'])} active schedules")


class TestLinkedInAgentEdgeCases:
    """Edge case tests for LinkedIn Agent"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if login_response.status_code != 200:
            pytest.skip("Authentication failed")
        
        yield
        
        self.session.post(f"{BASE_URL}/api/auth/logout")
    
    def test_disconnect_nonexistent_account(self):
        """DELETE /api/linkedin/accounts/{id} with invalid ID returns 404"""
        response = self.session.delete(f"{BASE_URL}/api/linkedin/accounts/nonexistent-id-12345")
        
        assert response.status_code == 404, f"Expected 404 for nonexistent account, got {response.status_code}"
        print("✓ Disconnect nonexistent account correctly returns 404")
    
    def test_set_company_for_nonexistent_account(self):
        """PUT /api/linkedin/accounts/{id}/company with invalid ID returns 404"""
        response = self.session.put(
            f"{BASE_URL}/api/linkedin/accounts/nonexistent-id-12345/company?company=fundle"
        )
        
        assert response.status_code == 404, f"Expected 404 for nonexistent account, got {response.status_code}"
        print("✓ Set company for nonexistent account correctly returns 404")
    
    def test_schedule_for_nonexistent_account(self):
        """POST /api/linkedin/schedule with invalid account_id returns 404"""
        response = self.session.post(
            f"{BASE_URL}/api/linkedin/schedule",
            json={
                "account_id": "nonexistent-id-12345",
                "company": "fundle",
                "interval_hours": 4,
                "enabled": True
            }
        )
        
        assert response.status_code == 404, f"Expected 404 for nonexistent account, got {response.status_code}"
        print("✓ Schedule for nonexistent account correctly returns 404")


class TestExistingAgentsStillWork:
    """Verify existing agents (Invoicing, Refund, Stock) still work"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if login_response.status_code != 200:
            pytest.skip("Authentication failed")
        
        yield
        
        self.session.post(f"{BASE_URL}/api/auth/logout")
    
    def test_agents_list_includes_all_four(self):
        """GET /api/agents returns all 4 agents including LinkedIn"""
        response = self.session.get(f"{BASE_URL}/api/agents")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "agents" in data, "Response should contain 'agents'"
        
        agents = data["agents"]
        assert len(agents) == 4, f"Expected 4 agents, got {len(agents)}"
        
        agent_ids = [a["id"] for a in agents]
        assert "invoicing" in agent_ids, "Invoicing agent should be present"
        assert "refund" in agent_ids, "Refund agent should be present"
        assert "stocks" in agent_ids, "Stock Investor agent should be present"
        assert "linkedin" in agent_ids, "LinkedIn agent should be present"
        
        print(f"✓ All 4 agents present: {agent_ids}")
    
    def test_invoices_endpoint_works(self):
        """GET /api/invoices still works"""
        response = self.session.get(f"{BASE_URL}/api/invoices")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "invoices" in data, "Response should contain 'invoices'"
        
        print(f"✓ Invoices endpoint works, returned {len(data['invoices'])} invoices")
    
    def test_refund_history_endpoint_works(self):
        """GET /api/refund/history still works"""
        response = self.session.get(f"{BASE_URL}/api/refund/history")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "history" in data, "Response should contain 'history'"
        
        print(f"✓ Refund history endpoint works, returned {len(data['history'])} items")
    
    def test_stocks_portfolio_endpoint_works(self):
        """GET /api/stocks/portfolio still works"""
        response = self.session.get(f"{BASE_URL}/api/stocks/portfolio")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "portfolio" in data, "Response should contain 'portfolio'"
        
        print(f"✓ Stocks portfolio endpoint works, returned {len(data['portfolio'])} positions")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
