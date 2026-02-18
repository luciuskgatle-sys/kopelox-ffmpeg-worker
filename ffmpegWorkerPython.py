# DUMMY WORKER - Proves Pipeline Works
# Returns instant success - NO offset detection

import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class DummyHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    
    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'healthy', 'mode': 'DUMMY'}).encode())
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            job_contract = json.loads(body)
            
            job_type = job_contract.get('job_type')
            job_id = job_contract.get('job_id', 'unknown')
            contribution_id = job_contract.get('contribution_id', 'unknown')
            
            print(f"[DUMMY] Received {job_type} job {job_id}")
            
            # INSTANT DUMMY RESPONSE
            result = {
                'success': True,
                'job_id': job_id,
                'contribution_id': contribution_id,
                'job_type': job_type,
                'offset_seconds': 1.23,
                'confidence_score': 0.85,
                'algorithm': 'DUMMY_TEST',
                'message': 'Pipeline test - no actual processing'
            }
            
            print(f"[DUMMY] Returning success for {job_id}")
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            
        except Exception as e:
            print(f"[DUMMY ERROR] {str(e)}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def log_message(self, format, *args):
        print(f"[DUMMY] {format % args}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    print("=" * 60)
    print("DUMMY WORKER ACTIVE - No Processing")
    print("Returns instant success for pipeline testing")
    print(f"Listening on port {port}")
    print("=" * 60)
    server.serve_forever()
