"""
AES-GCM Packet Encryption - Echo-Sign 2.0
==========================================
Syllabus Coverage: Unit IV - Block Ciphers & AES

Unit IV Concepts:
-----------------
1. Block ciphers vs stream ciphers
2. AES (Advanced Encryption Standard)
3. Modes of operation (GCM - Galois/Counter Mode)
4. Authenticated encryption (AEAD)
5. Nonce/IV management
6. Authentication tags

AES-GCM Properties:
-------------------
- Block size: 128 bits (16 bytes)
- Key sizes: 128, 192, or 256 bits (we use 256)
- Nonce size: 96 bits (12 bytes) recommended
- Tag size: 128 bits (16 bytes) for authentication
- Mode: GCM (Galois/Counter Mode)
  - Provides both confidentiality AND authenticity
  - Detects tampering, prevents forgeries
  - Efficient (parallelizable)

Security:
---------
- Each packet encrypted with unique nonce
- Authentication tag prevents tampering
- Replay attack prevention via timestamps
- No IV reuse (nonce derived from counter + random)

Usage:
------
    from crypto.aes_encryptor import AESEncryptor
    
    # Initialize with key from DH exchange
    encryptor = AESEncryptor(aes_key)
    
    # Encrypt packet
    ciphertext = encryptor.encrypt(plaintext, seq_num=1)
    
    # Decrypt packet
    plaintext = encryptor.decrypt(ciphertext)
"""

import os
import struct
import time
import logging
from typing import Tuple, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AESEncryptor:
    """
    AES-256-GCM encryption for UDP packets.
    Implements Unit IV concepts.
    """
    
    def __init__(self, key: bytes):
        """
        Initialize AES encryptor.
        
        Args:
            key: 256-bit (32 byte) AES key from DH exchange
        """
        if len(key) != 32:
            raise ValueError(f"Key must be 32 bytes for AES-256, got {len(key)}")
            
        # Unit IV: Initialize AES-GCM cipher
        self.cipher = AESGCM(key)
        self.key = key
        
        # Security parameters
        self.max_age_seconds = 5  # Reject packets older than 5 seconds
        self.seen_nonces = set()  # Track nonces to prevent replay
        self.nonce_counter = 0
        
        logger.info("✅ AES-256-GCM encryptor initialized")
        logger.info(f"   Key size: {len(key)} bytes (256 bits)")
        logger.info(f"   Replay protection: {self.max_age_seconds} second window")
        
    def _generate_nonce(self, seq_num: int) -> bytes:
        """
        Generate unique nonce for each packet.
        Unit IV: Nonce generation (must be unique for each encryption)
        
        Nonce format (12 bytes):
        ┌────────────┬──────────────┬─────────────┐
        │  Counter   │  Seq Number  │   Random    │
        │  (4 bytes) │  (4 bytes)   │  (4 bytes)  │
        └────────────┴──────────────┴─────────────┘
        
        This ensures:
        - Uniqueness (counter increments)
        - Ordering (sequence number)
        - Unpredictability (random component)
        
        Args:
            seq_num: Packet sequence number
            
        Returns:
            12-byte nonce
        """
        self.nonce_counter += 1
        
        # Combine counter, sequence number, and random bytes
        nonce = struct.pack('!I', self.nonce_counter)  # Counter (4 bytes)
        nonce += struct.pack('!I', seq_num)             # Sequence (4 bytes)
        nonce += os.urandom(4)                          # Random (4 bytes)
        
        return nonce
        
    def encrypt(self, plaintext: bytes, seq_num: int, 
                associated_data: bytes = b'') -> bytes:
        """
        Encrypt packet with AES-GCM.
        Unit IV: AES encryption in GCM mode
        
        Process:
        1. Generate unique nonce
        2. Encrypt plaintext
        3. Compute authentication tag
        4. Return: nonce + ciphertext + tag + timestamp
        
        Packet Format (encrypted):
        ┌─────────────┬──────────────┬─────────────┬──────────────┐
        │   Nonce     │  Ciphertext  │  Auth Tag   │  Timestamp   │
        │  (12 bytes) │  (variable)  │ (16 bytes)  │  (8 bytes)   │
        └─────────────┴──────────────┴─────────────┴──────────────┘
        
        Args:
            plaintext: Data to encrypt
            seq_num: Packet sequence number
            associated_data: Additional authenticated data (not encrypted)
            
        Returns:
            Encrypted packet
        """
        # Generate unique nonce
        nonce = self._generate_nonce(seq_num)
        
        # Current timestamp for replay protection
        timestamp = int(time.time()).to_bytes(8, 'big')
        
        # Combine AAD with timestamp
        aad = associated_data + timestamp
        
        # Unit IV: AES-GCM encryption
        # Produces ciphertext + authentication tag
        ciphertext = self.cipher.encrypt(
            nonce,           # Unique per packet
            plaintext,       # Data to encrypt
            aad              # Authenticated but not encrypted
        )
        
        # Pack: nonce + ciphertext (includes tag) + timestamp
        packet = nonce + ciphertext + timestamp
        
        return packet
        
    def decrypt(self, packet: bytes, 
                associated_data: bytes = b'') -> Tuple[bytes, int]:
        """
        Decrypt packet with AES-GCM.
        Unit IV: AES decryption and authentication verification
        
        Process:
        1. Extract nonce, ciphertext, tag, timestamp
        2. Check timestamp (replay protection)
        3. Check nonce hasn't been seen (replay protection)
        4. Decrypt and verify authentication tag
        5. Return plaintext
        
        Args:
            packet: Encrypted packet
            associated_data: Additional authenticated data
            
        Returns:
            (plaintext, timestamp) tuple
            
        Raises:
            Exception: If decryption fails or packet invalid
        """
        if len(packet) < 12 + 16 + 8:  # nonce + min_ciphertext + timestamp
            raise ValueError("Packet too short")
            
        # Extract components
        nonce = packet[:12]
        timestamp_bytes = packet[-8:]
        ciphertext = packet[12:-8]  # Includes auth tag
        
        # Parse timestamp
        timestamp = int.from_bytes(timestamp_bytes, 'big')
        
        # Unit IV: Replay attack prevention
        # Check if packet is too old
        current_time = int(time.time())
        age = current_time - timestamp
        
        if age > self.max_age_seconds:
            raise ValueError(f"Packet too old ({age} seconds)")
            
        if age < -2:  # Allow 2 second clock skew
            raise ValueError(f"Packet from future (clock skew)")
            
        # Check if nonce already seen (prevent replay)
        if nonce in self.seen_nonces:
            raise ValueError("Duplicate nonce detected (replay attack?)")
            
        # Combine AAD with timestamp
        aad = associated_data + timestamp_bytes
        
        try:
            # Unit IV: AES-GCM decryption and authentication
            # Verifies authentication tag, raises exception if tampered
            plaintext = self.cipher.decrypt(
                nonce,
                ciphertext,
                aad
            )
            
            # Record nonce to prevent replay
            self.seen_nonces.add(nonce)
            
            # Cleanup old nonces (prevent memory growth)
            if len(self.seen_nonces) > 10000:
                self.seen_nonces.clear()
                logger.debug("Cleared nonce cache")
                
            return plaintext, timestamp
            
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")
            
    def get_overhead(self) -> int:
        """Get encryption overhead in bytes."""
        return 12 + 16 + 8  # nonce + tag + timestamp = 36 bytes


def test_aes_encryption():
    """Test AES-GCM encryption."""
    logger.info("=" * 60)
    logger.info("Testing AES-GCM Encryption (Unit IV)")
    logger.info("=" * 60)
    
    # Generate test key (in real use, from DH exchange)
    test_key = os.urandom(32)
    
    # Test 1: Basic encryption/decryption
    logger.info("\n1. Testing basic encryption/decryption...")
    
    encryptor = AESEncryptor(test_key)
    decryptor = AESEncryptor(test_key)
    
    plaintext = b"Hello, this is a secret ISL landmark packet!"
    logger.info(f"   Plaintext: {plaintext}")
    logger.info(f"   Plaintext size: {len(plaintext)} bytes")
    
    # Encrypt
    ciphertext = encryptor.encrypt(plaintext, seq_num=1)
    logger.info(f"   Ciphertext size: {len(ciphertext)} bytes")
    logger.info(f"   Overhead: {len(ciphertext) - len(plaintext)} bytes")
    
    # Decrypt
    decrypted, timestamp = decryptor.decrypt(ciphertext)
    logger.info(f"   Decrypted: {decrypted}")
    logger.info(f"   Timestamp: {timestamp}")
    
    assert plaintext == decrypted, "Decryption failed!"
    logger.info("   ✅ Encryption/Decryption successful")
    
    # Test 2: Multiple packets
    logger.info("\n2. Testing multiple packets...")
    
    for i in range(5):
        msg = f"Packet {i}".encode()
        encrypted = encryptor.encrypt(msg, seq_num=i)
        decrypted, _ = decryptor.decrypt(encrypted)
        assert msg == decrypted
        logger.info(f"   Packet {i}: ✅")
        
    logger.info("   ✅ Multiple packets successful")
    
    # Test 3: Tampering detection
    logger.info("\n3. Testing tampering detection...")
    
    plaintext = b"Important data"
    encrypted = encryptor.encrypt(plaintext, seq_num=10)
    
    # Tamper with ciphertext
    tampered = bytearray(encrypted)
    tampered[20] ^= 0xFF  # Flip some bits
    
    try:
        decryptor.decrypt(bytes(tampered))
        logger.error("   ❌ Tampering not detected!")
        assert False
    except ValueError:
        logger.info("   ✅ Tampering detected correctly")
        
    # Test 4: Replay attack prevention
    logger.info("\n4. Testing replay attack prevention...")
    
    plaintext = b"One-time message"
    encrypted = encryptor.encrypt(plaintext, seq_num=20)
    
    # First decryption succeeds
    decryptor.decrypt(encrypted)
    logger.info("   First decryption: ✅")
    
    # Second decryption (replay) should fail
    try:
        decryptor.decrypt(encrypted)
        logger.error("   ❌ Replay not detected!")
        assert False
    except ValueError:
        logger.info("   ✅ Replay attack prevented")
        
    # Test 5: Old packet rejection
    logger.info("\n5. Testing old packet rejection...")
    
    plaintext = b"Old message"
    encrypted = encryptor.encrypt(plaintext, seq_num=30)
    
    # Wait 6 seconds (longer than max_age)
    logger.info("   Waiting 6 seconds...")
    import time as time_module
    time_module.sleep(6)
    
    try:
        decryptor.decrypt(encrypted)
        logger.error("   ❌ Old packet not rejected!")
        assert False
    except ValueError as e:
        logger.info(f"   ✅ Old packet rejected: {e}")
        
    logger.info("\n" + "=" * 60)
    logger.info("✅ All AES-GCM tests passed!")
    logger.info("=" * 60)


if __name__ == '__main__':
    test_aes_encryption()
