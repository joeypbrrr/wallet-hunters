import unittest,requests
from research import FetchQueue,CHAINS
class RPCFailoverTest(unittest.TestCase):
 def test_429_suspend_host_and_use_independent_public_provider(self):
  q=FetchQueue();calls=[]
  def request(url,payload):
   calls.append((url,payload['method']))
   if url==CHAINS['solana']['rpc']:
    response=requests.Response();response.status_code=429;raise requests.HTTPError('quota',response=response)
   return {'result':42}
  q.request=request
  self.assertEqual(q.rpc('solana','getSlot'),42);self.assertEqual(q.rpc('solana','getTransaction',['sample-test-tx']),42)
  self.assertEqual(len(calls),3);self.assertIn('solana-rpc.publicnode.com',q.suspended);self.assertEqual(q.rpc_routes['solana'],'https://api.mainnet-beta.solana.com')
 def test_permission_denial_never_bypassed(self):
  q=FetchQueue();calls=[]
  def request(url,payload):
   calls.append(url);response=requests.Response();response.status_code=403;raise requests.HTTPError('permission denied',response=response)
  q.request=request
  with self.assertRaises(requests.HTTPError):q.rpc('solana','getSlot')
  self.assertEqual(len(calls),1)
