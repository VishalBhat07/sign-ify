"""
RSA Key Management - Echo-Sign 2.0
===================================
Syllabus Coverage: Unit IV - RSA Cryptography

Unit IV Concepts:
-----------------
1. Public key cryptography
2. RSA algorithm (Rivest-Shamir-Adleman)
3. Key generation (p, q, n, e, d)
4. Encryption/Decryption
5. Digital signatures
6. Key persistence and distribution

RSA Mathematics:
----------------
1. Choose two large primes p and q
2. Compute n = p × q (modulus)
3. Compute φ(n) = (p-1)(q-1) (Euler's totient)
4. Choose e (public exponent, typically 65537)
5. Compute d = e^(-1) mod φ(n) (private exponent)

Public key: (e, n)
Private key: (d, n)

Encryption: c = m^e mod n
Decryption: m = c^d mod n

Security:
---------
- Key size: 2048 bits (minimum), 4096 bits (recommended)
- Padding: OAEP (Optimal Asymmetric Encryption Padding)
- Signature: PSS (Probabilistic Signature Scheme)

Usage:
------
    from crypto.rsa_manager import RSAKeyManager
    
    # Alice generates keypair
    alice_rsa = RSAKeyManager()
    alice_rsa.generate_keypair()
    
    # Alice exports public key
    alice_public = alice_rsa.export_public_key()
    
    # Bob imports Alice's public key
    bob_rsa = RSAKeyManager()
    bob_rsa.import_public_key(alice_public)
    
    # Bob encrypts message for Alice
    ciphertext = bob_rsa.encrypt(b"Hello Alice!")
    
    # Alice decrypts with her private key
    plaintext = alice_rsa.decrypt(ciphertext)
"""

import os
import logging
from typing import Tuple, Optional
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RSAKeyManager:
    """
    RSA key management for Echo-Sign 2.0.
    Handles key generation, encryption, decryption, and digital signatures.
    Implements Unit IV concepts.
    """
    
    def __init__(self):
        """Initialize RSA manager."""
        self.private_key = None
        self.public_key = None
        
    def generate_keypair(self, key_size: int = 4096):
        """
        Generate RSA keypair.
        Unit IV: RSA key generation algorithm
        
        Process:
        1. Generate two large primes p, q
        2. Compute n = p × q
        3. Compute φ(n) = (p-1)(q-1)
        4. Choose e = 65537 (common choice)
        5. Compute d = e^(-1) mod φ(n)
        
        Args:
            key_size: Key size in bits (2048, 3072, or 4096)
        """
        logger.info(f"🔐 Generating {key_size}-bit RSA keypair...")
        logger.info("   This may take 5-10 seconds...")
        
        # Unit IV: RSA key generation
        # cryptography library implements the full algorithm
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,  # Common choice for e
            key_size=key_size,
            backend=default_backend()
        )
        
        # Extract public key from private key
        self.public_key = self.private_key.public_key()
        
        # Log key parameters
        private_numbers = self.private_key.private_numbers()
        public_numbers = private_numbers.public_numbers
        
        logger.info("✅ RSA keypair generated successfully")
        logger.info(f"   Modulus (n): {public_numbers.n.bit_length()} bits")
        logger.info(f"   Public exponent (e): {public_numbers.e}")
        logger.info(f"   Private exponent (d): {private_numbers.d.bit_length()} bits")
        
    def export_public_key(self) -> bytes:
        """
        Export public key in PEM format.
        Unit IV: Key distribution
        
        Returns:
            Public key as PEM-encoded bytes
        """
        if not self.public_key:
            raise ValueError("No public key available. Generate or import a key first.")
            
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return pem
        
    def import_public_key(self, pem_data: bytes):
        """
        Import public key from PEM format.
        Unit IV: Key distribution
        
        Args:
            pem_data: PEM-encoded public key
        """
        self.public_key = serialization.load_pem_public_key(
            pem_data,
            backend=default_backend()
        )
        
        logger.info("✅ Public key imported")
        
    def export_private_key(self, password: Optional[bytes] = None) -> bytes:
        """
        Export private key in PEM format.
        Unit IV: Key persistence
        
        Args:
            password: Optional password for encryption
            
        Returns:
            Private key as PEM-encoded bytes
        """
        if not self.private_key:
            raise ValueError("No private key available. Generate a keypair first.")
            
        if password:
            encryption = serialization.BestAvailableEncryption(password)
        else:
            encryption = serialization.NoEncryption()
            
        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption
        )
        
        return pem
        
    def import_private_key(self, pem_data: bytes, password: Optional[bytes] = None):
        """
        Import private key from PEM format.
        Unit IV: Key persistence
        
        Args:
            pem_data: PEM-encoded private key
            password: Password if key is encrypted
        """
        self.private_key = serialization.load_pem_private_key(
            pem_data,
            password=password,
            backend=default_backend()
        )
        
        self.public_key = self.private_key.public_key()
        
        logger.info("✅ Private key imported")
        
    def encrypt(self, plaintext: bytes) -> bytes:
        """
        Encrypt data with RSA public key.
        Unit IV: RSA encryption (c = m^e mod n)
        
        Uses OAEP padding for security:
        - Randomized padding
        - Protection against chosen ciphertext attacks
        
        Args:
            plaintext: Data to encrypt (max 470 bytes for 4096-bit key)
            
        Returns:
            Ciphertext
        """
        if not self.public_key:
            raise ValueError("No public key available")
            
        # Unit IV: RSA encryption with OAEP padding
        ciphertext = self.public_key.encrypt(
            plaintext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return ciphertext
        
    def decrypt(self, ciphertext: bytes) -> bytes:
        """
        Decrypt data with RSA private key.
        Unit IV: RSA decryption (m = c^d mod n)
        
        Args:
            ciphertext: Encrypted data
            
        Returns:
            Plaintext
        """
        if not self.private_key:
            raise ValueError("No private key available")
            
        # Unit IV: RSA decryption with OAEP padding
        plaintext = self.private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return plaintext
        
    def sign(self, message: bytes) -> bytes:
        """
        Create digital signature.
        Unit IV: Digital signatures for authentication
        
        Process:
        1. Hash the message (SHA-256)
        2. Sign the hash with private key
        3. Return signature
        
        Args:
            message: Data to sign
            
        Returns:
            Digital signature
        """
        if not self.private_key:
            raise ValueError("No private key available")
            
        # Unit IV: Digital signature with PSS padding
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return signature
        
    def verify(self, message: bytes, signature: bytes) -> bool:
        """
        Verify digital signature.
        Unit IV: Signature verification
        
        Args:
            message: Original message
            signature: Signature to verify
            
        Returns:
            True if signature valid, False otherwise
        """
        if not self.public_key:
            raise ValueError("No public key available")
            
        try:
            # Unit IV: Signature verification
            self.public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False


def test_rsa():
    """Test RSA operations."""
    logger.info("=" * 60)
    logger.info("Testing RSA Key Management (Unit IV)")
    logger.info("=" * 60)
    
    # Test 1: Key generation
    logger.info("\n1. Testing key generation...")
    rsa_mgr = RSAKeyManager()
    rsa_mgr.generate_keypair(key_size=2048)  # 2048 for faster testing
    
    # Test 2: Encryption/Decryption
    logger.info("\n2. Testing encryption/decryption...")
    plaintext = b"Hello, this is a secret message!"
    logger.info(f"   Plaintext: {plaintext}")
    
    ciphertext = rsa_mgr.encrypt(plaintext)
    logger.info(f"   Ciphertext length: {len(ciphertext)} bytes")
    
    decrypted = rsa_mgr.decrypt(ciphertext)
    logger.info(f"   Decrypted: {decrypted}")
    
    assert plaintext == decrypted, "Decryption failed!"
    logger.info("   ✅ Encryption/Decryption successful")
    
    # Test 3: Digital signatures
    logger.info("\n3. Testing digital signatures...")
    message = b"Sign this important document"
    signature = rsa_mgr.sign(message)
    logger.info(f"   Signature length: {len(signature)} bytes")
    
    is_valid = rsa_mgr.verify(message, signature)
    logger.info(f"   Signature valid: {is_valid}")
    assert is_valid, "Signature verification failed!"
    logger.info("   ✅ Signature verification successful")
    
    # Test 4: Key export/import
    logger.info("\n4. Testing key persistence...")
    public_pem = rsa_mgr.export_public_key()
    logger.info(f"   Public key exported ({len(public_pem)} bytes)")
    
    new_rsa = RSAKeyManager()
    new_rsa.import_public_key(public_pem)
    
    # Test encryption with imported public key
    ciphertext2 = new_rsa.encrypt(plaintext)
    decrypted2 = rsa_mgr.decrypt(ciphertext2)
    assert plaintext == decrypted2
    logger.info("   ✅ Key persistence successful")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ All RSA tests passed!")
    logger.info("=" * 60)


if __name__ == '__main__':
    test_rsa()
