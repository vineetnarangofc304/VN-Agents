#!/usr/bin/env python3

import requests
import sys
import os
import tempfile
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

class InvoiceAgentAPITester:
    def __init__(self, base_url="https://agent-builder-133.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.session = requests.Session()
        self.tests_run = 0
        self.tests_passed = 0
        self.test_invoice_id = None

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED {details}")
        else:
            print(f"❌ {name} - FAILED {details}")
        return success

    def create_test_pdf(self, filename="test_invoice.pdf"):
        """Create a test PDF file with 2 pages and 'Page 1 of 2' text"""
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, filename)
        
        c = canvas.Canvas(filepath, pagesize=letter)
        
        # Page 1
        c.drawString(100, 750, "Google Invoice")
        c.drawString(100, 700, "Invoice #12345")
        c.drawString(100, 650, "Date: 2024-01-15")
        c.drawString(100, 600, "Amount: $100.00")
        c.drawString(300, 50, "Page 1 of 2")  # This should be changed to "Page 1 of 1"
        c.showPage()
        
        # Page 2 (should be removed)
        c.drawString(100, 750, "Additional Details")
        c.drawString(100, 700, "Terms and Conditions")
        c.drawString(300, 50, "Page 2 of 2")
        c.showPage()
        
        c.save()
        return filepath

    def test_login(self):
        """Test login endpoint"""
        try:
            response = self.session.post(f"{self.api_url}/auth/login", json={
                "email": "vineetnarangofc@gmail.com",
                "password": "InvoiceAgent@2024!"
            })
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["id", "email", "name", "role"]
                if all(field in data for field in required_fields):
                    return self.log_test("Login", True, f"- User: {data['name']} ({data['email']})")
                else:
                    return self.log_test("Login", False, f"- Missing fields in response: {data}")
            else:
                return self.log_test("Login", False, f"- Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            return self.log_test("Login", False, f"- Error: {str(e)}")

    def test_get_me(self):
        """Test get current user endpoint"""
        try:
            response = self.session.get(f"{self.api_url}/auth/me")
            
            if response.status_code == 200:
                data = response.json()
                if "email" in data and data["email"] == "vineetnarangofc@gmail.com":
                    return self.log_test("Get Current User", True, f"- Email: {data['email']}")
                else:
                    return self.log_test("Get Current User", False, f"- Unexpected user data: {data}")
            else:
                return self.log_test("Get Current User", False, f"- Status: {response.status_code}")
                
        except Exception as e:
            return self.log_test("Get Current User", False, f"- Error: {str(e)}")

    def test_get_invoices_empty(self):
        """Test get invoices endpoint (should be empty initially)"""
        try:
            response = self.session.get(f"{self.api_url}/invoices")
            
            if response.status_code == 200:
                data = response.json()
                if "invoices" in data and isinstance(data["invoices"], list):
                    return self.log_test("Get Invoices (Empty)", True, f"- Count: {len(data['invoices'])}")
                else:
                    return self.log_test("Get Invoices (Empty)", False, f"- Invalid response format: {data}")
            else:
                return self.log_test("Get Invoices (Empty)", False, f"- Status: {response.status_code}")
                
        except Exception as e:
            return self.log_test("Get Invoices (Empty)", False, f"- Error: {str(e)}")

    def test_upload_invoice(self):
        """Test invoice upload endpoint"""
        try:
            # Create test PDF
            pdf_path = self.create_test_pdf()
            
            with open(pdf_path, 'rb') as f:
                files = {'files': ('test_invoice.pdf', f, 'application/pdf')}
                response = self.session.post(f"{self.api_url}/invoices/upload", files=files)
            
            # Clean up test file
            os.remove(pdf_path)
            
            if response.status_code == 200:
                data = response.json()
                if "results" in data and len(data["results"]) > 0:
                    result = data["results"][0]
                    if result.get("status") == "processed" and "id" in result:
                        self.test_invoice_id = result["id"]
                        return self.log_test("Upload Invoice", True, f"- ID: {result['id']}")
                    else:
                        return self.log_test("Upload Invoice", False, f"- Processing failed: {result}")
                else:
                    return self.log_test("Upload Invoice", False, f"- No results in response: {data}")
            else:
                return self.log_test("Upload Invoice", False, f"- Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            return self.log_test("Upload Invoice", False, f"- Error: {str(e)}")

    def test_get_invoices_with_data(self):
        """Test get invoices endpoint (should have data after upload)"""
        try:
            response = self.session.get(f"{self.api_url}/invoices")
            
            if response.status_code == 200:
                data = response.json()
                if "invoices" in data and len(data["invoices"]) > 0:
                    invoice = data["invoices"][0]
                    required_fields = ["id", "original_filename", "upload_date", "status"]
                    if all(field in invoice for field in required_fields):
                        return self.log_test("Get Invoices (With Data)", True, f"- Count: {len(data['invoices'])}, Status: {invoice['status']}")
                    else:
                        return self.log_test("Get Invoices (With Data)", False, f"- Missing fields: {invoice}")
                else:
                    return self.log_test("Get Invoices (With Data)", False, f"- No invoices found: {data}")
            else:
                return self.log_test("Get Invoices (With Data)", False, f"- Status: {response.status_code}")
                
        except Exception as e:
            return self.log_test("Get Invoices (With Data)", False, f"- Error: {str(e)}")

    def test_download_original(self):
        """Test download original invoice endpoint"""
        if not self.test_invoice_id:
            return self.log_test("Download Original", False, "- No invoice ID available")
        
        try:
            response = self.session.get(f"{self.api_url}/invoices/{self.test_invoice_id}/original")
            
            if response.status_code == 200:
                if response.headers.get('content-type') == 'application/pdf':
                    return self.log_test("Download Original", True, f"- PDF size: {len(response.content)} bytes")
                else:
                    return self.log_test("Download Original", False, f"- Wrong content type: {response.headers.get('content-type')}")
            else:
                return self.log_test("Download Original", False, f"- Status: {response.status_code}")
                
        except Exception as e:
            return self.log_test("Download Original", False, f"- Error: {str(e)}")

    def test_download_edited(self):
        """Test download edited invoice endpoint"""
        if not self.test_invoice_id:
            return self.log_test("Download Edited", False, "- No invoice ID available")
        
        try:
            response = self.session.get(f"{self.api_url}/invoices/{self.test_invoice_id}/edited")
            
            if response.status_code == 200:
                if response.headers.get('content-type') == 'application/pdf':
                    return self.log_test("Download Edited", True, f"- PDF size: {len(response.content)} bytes")
                else:
                    return self.log_test("Download Edited", False, f"- Wrong content type: {response.headers.get('content-type')}")
            else:
                return self.log_test("Download Edited", False, f"- Status: {response.status_code}")
                
        except Exception as e:
            return self.log_test("Download Edited", False, f"- Error: {str(e)}")

    def test_download_all_zip(self):
        """Test download all edited invoices as ZIP"""
        try:
            response = self.session.get(f"{self.api_url}/invoices/download-all")
            
            if response.status_code == 200:
                if response.headers.get('content-type') == 'application/zip':
                    return self.log_test("Download All ZIP", True, f"- ZIP size: {len(response.content)} bytes")
                else:
                    return self.log_test("Download All ZIP", False, f"- Wrong content type: {response.headers.get('content-type')}")
            else:
                return self.log_test("Download All ZIP", False, f"- Status: {response.status_code}")
                
        except Exception as e:
            return self.log_test("Download All ZIP", False, f"- Error: {str(e)}")

    def test_delete_invoice(self):
        """Test delete invoice endpoint"""
        if not self.test_invoice_id:
            return self.log_test("Delete Invoice", False, "- No invoice ID available")
        
        try:
            response = self.session.delete(f"{self.api_url}/invoices/{self.test_invoice_id}")
            
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    return self.log_test("Delete Invoice", True, f"- Message: {data['message']}")
                else:
                    return self.log_test("Delete Invoice", False, f"- No message in response: {data}")
            else:
                return self.log_test("Delete Invoice", False, f"- Status: {response.status_code}")
                
        except Exception as e:
            return self.log_test("Delete Invoice", False, f"- Error: {str(e)}")

    def test_logout(self):
        """Test logout endpoint"""
        try:
            response = self.session.post(f"{self.api_url}/auth/logout")
            
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    return self.log_test("Logout", True, f"- Message: {data['message']}")
                else:
                    return self.log_test("Logout", False, f"- No message in response: {data}")
            else:
                return self.log_test("Logout", False, f"- Status: {response.status_code}")
                
        except Exception as e:
            return self.log_test("Logout", False, f"- Error: {str(e)}")

    def test_auth_after_logout(self):
        """Test that auth is required after logout"""
        try:
            response = self.session.get(f"{self.api_url}/auth/me")
            
            if response.status_code == 401:
                return self.log_test("Auth After Logout", True, "- Correctly returns 401")
            else:
                return self.log_test("Auth After Logout", False, f"- Expected 401, got {response.status_code}")
                
        except Exception as e:
            return self.log_test("Auth After Logout", False, f"- Error: {str(e)}")

    def run_all_tests(self):
        """Run all API tests in sequence"""
        print("🚀 Starting Invoice Agent API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Authentication tests
        print("\n🔐 Authentication Tests:")
        self.test_login()
        self.test_get_me()
        
        # Invoice management tests
        print("\n📄 Invoice Management Tests:")
        self.test_get_invoices_empty()
        self.test_upload_invoice()
        self.test_get_invoices_with_data()
        
        # Download tests
        print("\n⬇️ Download Tests:")
        self.test_download_original()
        self.test_download_edited()
        self.test_download_all_zip()
        
        # Cleanup tests
        print("\n🗑️ Cleanup Tests:")
        self.test_delete_invoice()
        
        # Logout tests
        print("\n🚪 Logout Tests:")
        self.test_logout()
        self.test_auth_after_logout()
        
        # Summary
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        success_rate = (self.tests_passed / self.tests_run) * 100 if self.tests_run > 0 else 0
        print(f"✨ Success Rate: {success_rate:.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("⚠️ Some tests failed!")
            return 1

def main():
    tester = InvoiceAgentAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())