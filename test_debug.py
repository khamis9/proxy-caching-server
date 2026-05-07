import sys
sys.path.insert(0, 'src')
from filter import RequestFilter

# Just test the filter directly
f = RequestFilter(
    blocked_hosts={'blocked.test', 'ads.example'},
    blocked_keywords={'forbidden', 'malware'},
    blocked_ips={'104.20.23.154'}
)

print('Testing Filter IP Blocking')
print('=' * 60)

# Test 1: example.com (should be blocked by IP)
is_blocked1, reason1 = f.is_blocked(host='example.com', resource='/')
print(f'Test 1: example.com')
print(f'  is_blocked: {is_blocked1}')
print(f'  reason: {reason1}')
print()

# Test 2: google.com (should NOT be blocked)
is_blocked2, reason2 = f.is_blocked(host='google.com', resource='/')
print(f'Test 2: google.com')
print(f'  is_blocked: {is_blocked2}')
print(f'  reason: {reason2}')
print()

# Check the blocked_ips
print(f'Blocked IPs in filter: {f.blocked_ips}')
