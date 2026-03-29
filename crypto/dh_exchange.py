"""
Diffie-Hellman Key Exchange - Echo-Sign 2.0
============================================
Syllabus Coverage: Unit IV - Diffie-Hellman Key Exchange

Unit IV Concepts:
-----------------
1. Diffie-Hellman protocol
2. Discrete logarithm problem
3. Shared secret computation
4. Key derivation functions (KDF)
5. Perfect Forward Secrecy (PFS)

Mathematics:
------------
Alice and Bob agree on public parameters (p, g):
- p: large prime modulus
- g: generator (primitive root mod p)

1. Alice generates private key a, computes A = g^a mod p
2. Bob generates private key b, computes B = g^b mod p
3. They exchange A and B (public values)
4. Alice computes s = B^a mod p
5. Bob computes s = A^b mod p
6. Both have same shared secret s = g^(ab) mod p

Security:
---------
- Key size: 2048 bits (minimum recommended)
- Ephemeral keys: New keypair for each session (PFS)
- Authenticated: Combined with RSA signatures to prevent MITM

Usage:
------
    from crypto.dh_exchange import DHKeyExchange
    
    # Alice side
    alice_dh = DHKeyExchange()
    alice_dh.generate_parameters()  # Or use pre-generated
    alice_public = alice_dh.generate_keypair()
    
    # Bob side
    bob_dh = DHKeyExchange(alice_dh.get_parameters())
    bob_public = bob_dh.generate_keypair()
    
    # Exchange public keys
    alice_shared = alice_dh.compute_shared_secret(bob_public)
    bob_shared = bob_dh.compute_shared_secret(alice_public)
    
    # Derive AES key
    alice_aes_key = alice_dh.derive_key(alice_shared)
    bob_aes_key = bob_dh.derive_key(bob_shared)
    
    # alice_aes_key == bob_aes_key ✅
"""

import os
import logging
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DHKeyExchange:
    """
    Diffie-Hellman Ephemeral (DHE) key exchange.
    Implements Unit IV concepts.
    """
    
    def __init__(self, parameters=None):
        """
        Initialize DH key exchange.
        
        Args:
            parameters: Shared DH parameters (p, g) or None to generate new
        """
        self.parameters = parameters
        self.private_key = None
        self.public_key = None
        self.shared_secret = None
        
    def generate_parameters(self, key_size: int = 2048):
        """
        Generate DH parameters (p, g).
        Unit IV: Choose large prime p and generator g
        
        Warning: This is SLOW (30-60 seconds for 2048-bit)!
        In production, use pre-generated parameters.
        
        Args:
            key_size: Size of prime modulus p (2048, 3072, or 4096)
        """
        logger.info(f"🔐 Generating {key_size}-bit DH parameters...")
        logger.info("   ⚠️  This will take 30-60 seconds...")
        logger.info("   (In production, use pre-generated parameters)")
        
        # Unit IV: Generate parameters
        # 1. Find large prime p
        # 2. Find generator g (primitive root mod p)
        self.parameters = dh.generate_parameters(
            generator=2,  # Common generator choice
            key_size=key_size,
            backend=default_backend()
        )
        
        # Extract parameters for display
        param_numbers = self.parameters.parameter_numbers()
        logger.info("✅ DH parameters generated")
        logger.info(f"   Generator (g): {param_numbers.g}")
        logger.info(f"   Prime size (p): {key_size} bits")
        
        return self.parameters
        
    def load_standard_parameters(self):
        """
        Load RFC 3526 standard DH parameters (Group 14 - 2048-bit).
        Unit IV: Using well-known, vetted parameters
        
        Advantage: Instant (no generation time)
        Security: Vetted by cryptographers, widely used
        """
        # RFC 3526 Group 14 parameters (2048-bit MODP)
        p = int(
            'FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1'
            '29024E088A67CC74020BBEA63B139B22514A08798E3404DD'
            'EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245'
            'E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED'
            'EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D'
            'C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F'
            '83655D23DCA3AD961C62F356208552BB9ED529077096966D'
            '670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B'
            'E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9'
            'DE2BCBF6955817183995497CEA956AE515D2261898FA0510'
            '15728E5A8AACAA68FFFFFFFFFFFFFFFF', 16
        )
        g = 2
        
        # Create parameters object
        param_numbers = dh.DHParameterNumbers(p, g)
        self.parameters = param_numbers.parameters(default_backend())
        
        logger.info("✅ Loaded RFC 3526 DH parameters (Group 14)")
        logger.info(f"   Generator: {g}")
        logger.info(f"   Prime size: 2048 bits")
        
        return self.parameters
        
    def get_parameters(self):
        """Get current DH parameters."""
        return self.parameters
        
    def generate_keypair(self) -> bytes:
        """
        Generate ephemeral DH keypair.
        Unit IV: Generate private key a and compute public key A = g^a mod p
        
        Returns:
            Public key bytes (to send to peer)
        """
        if not self.parameters:
            raise ValueError("Parameters not set. Call generate_parameters() or load_standard_parameters() first.")
            
        # Unit IV: Generate private key (random integer a)
        # Compute public key A = g^a mod p
        self.private_key = self.parameters.generate_private_key()
        self.public_key = self.private_key.public_key()
        
        # Serialize public key for transmission
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        logger.info("✅ DH keypair generated")
        logger.info(f"   Public key size: {len(public_bytes)} bytes")
        
        return public_bytes
        
    def compute_shared_secret(self, peer_public_key_bytes: bytes) -> bytes:
        """
        Compute shared secret.
        Unit IV: Compute s = B^a mod p (where B is peer's public key)
        
        Args:
            peer_public_key_bytes: Peer's DH public key (PEM format)
            
        Returns:
            Shared secret bytes
        """
        if not self.private_key:
            raise ValueError("Keypair not generated. Call generate_keypair() first.")
            
        # Deserialize peer's public key
        peer_public_key = serialization.load_pem_public_key(
            peer_public_key_bytes,
            backend=default_backend()
        )
        
        # Unit IV: Compute shared secret
        # If we have private key a and peer public key B:
        # shared_secret = B^a mod p = (g^b)^a mod p = g^(ab) mod p
        self.shared_secret = self.private_key.exchange(peer_public_key)
        
        logger.info("✅ Shared secret computed")
        logger.info(f"   Secret size: {len(self.shared_secret)} bytes")
        
        return self.shared_secret
        
    def derive_key(self, shared_secret: bytes = None, key_length: int = 32, 
                   info: bytes = b'echo-sign-aes-key') -> bytes:
        """
        Derive AES key from shared secret using HKDF.
        Unit IV: Key derivation function (KDF)
        
        HKDF = HMAC-based Key Derivation Function
        - Extracts cryptographic key material from shared secret
        - Produces uniformly random key
        - Can derive multiple keys from same secret
        
        Args:
            shared_secret: DH shared secret (default: use computed secret)
            key_length: Desired key length in bytes (32 = 256 bits for AES-256)
            info: Application-specific context string
            
        Returns:
            Derived AES key
        """
        if shared_secret is None:
            shared_secret = self.shared_secret
            
        if not shared_secret:
            raise ValueError("No shared secret available")
            
        # Unit IV: HKDF key derivation
        # HKDF(secret, salt, info, length) → key
        kdf = HKDF(
            algorithm=hashes.SHA256(),
            length=key_length,
            salt=None,  # Optional salt (we use None for simplicity)
            info=info,  # Context string to bind key to application
            backend=default_backend()
        )
        
        aes_key = kdf.derive(shared_secret)
        
        logger.info("✅ AES key derived")
        logger.info(f"   Key length: {len(aes_key)} bytes ({len(aes_key)*8} bits)")
        
        return aes_key


def test_dh():
    """Test Diffie-Hellman key exchange."""
    logger.info("=" * 60)
    logger.info("Testing Diffie-Hellman Key Exchange (Unit IV)")
    logger.info("=" * 60)
    
    # Test 1: Using standard parameters (fast)
    logger.info("\n1. Loading standard DH parameters...")
    
    # Alice side
    alice_dh = DHKeyExchange()
    alice_dh.load_standard_parameters()
    alice_public = alice_dh.generate_keypair()
    logger.info("   Alice generated keypair")
    
    # Bob side
    bob_dh = DHKeyExchange(alice_dh.get_parameters())
    bob_public = bob_dh.generate_keypair()
    logger.info("   Bob generated keypair")
    
    # Test 2: Exchange and compute shared secrets
    logger.info("\n2. Computing shared secrets...")
    
    alice_shared = alice_dh.compute_shared_secret(bob_public)
    bob_shared = bob_dh.compute_shared_secret(alice_public)
    
    logger.info(f"   Alice's shared secret: {alice_shared[:16].hex()}...")
    logger.info(f"   Bob's shared secret:   {bob_shared[:16].hex()}...")
    
    assert alice_shared == bob_shared, "Shared secrets don't match!"
    logger.info("   ✅ Shared secrets match!")
    
    # Test 3: Derive AES keys
    logger.info("\n3. Deriving AES keys...")
    
    alice_aes = alice_dh.derive_key(alice_shared)
    bob_aes = bob_dh.derive_key(bob_shared)
    
    logger.info(f"   Alice's AES key: {alice_aes.hex()}")
    logger.info(f"   Bob's AES key:   {bob_aes.hex()}")
    
    assert alice_aes == bob_aes, "AES keys don't match!"
    logger.info("   ✅ AES keys match!")
    
    # Test 4: Security property - different session keys
    logger.info("\n4. Testing Perfect Forward Secrecy...")
    
    # New session with new ephemeral keys
    alice_dh2 = DHKeyExchange()
    alice_dh2.load_standard_parameters()
    alice_public2 = alice_dh2.generate_keypair()
    
    bob_dh2 = DHKeyExchange(alice_dh2.get_parameters())
    bob_public2 = bob_dh2.generate_keypair()
    
    alice_shared2 = alice_dh2.compute_shared_secret(bob_public2)
    alice_aes2 = alice_dh2.derive_key(alice_shared2)
    
    logger.info(f"   Session 1 AES key: {alice_aes.hex()[:32]}...")
    logger.info(f"   Session 2 AES key: {alice_aes2.hex()[:32]}...")
    
    assert alice_aes != alice_aes2, "Keys should be different for different sessions!"
    logger.info("   ✅ Different sessions produce different keys (PFS working!)")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ All DH tests passed!")
    logger.info("=" * 60)


if __name__ == '__main__':
    test_dh()
