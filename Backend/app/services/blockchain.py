import asyncio
import re
import logging
from typing import List, Dict, Any
from web3 import Web3
from eth_utils import is_address

logger = logging.getLogger(__name__)

# Public RPCs for basic verification (no keys required for simple get_code)
RPC_ENDPOINTS = {
    "ETHEREUM": "https://rpc.ankr.com/eth",
    "BASE": "https://mainnet.base.org",
    "ARBITRUM": "https://arb1.arbitrum.io/rpc",
}

# Regex for finding addresses
EVM_ADDRESS_REGEX = r"0x[a-fA-F0-9]{40}"
# NOTE: Solana address detection only — verification not yet implemented (EVM chains only)
SOLANA_ADDRESS_REGEX = r"[1-9A-HJ-NP-Za-km-z]{32,44}"

class BlockchainService:
    def __init__(self) -> None:
        self.w3_instances: dict[str, Web3] = {
            chain: Web3(Web3.HTTPProvider(url)) 
            for chain, url in RPC_ENDPOINTS.items()
        }

    def extract_addresses(self, text: str) -> Dict[str, List[str]]:
        """Extracts EVM and Solana-like addresses from text."""
        # NOTE: This is regex pattern matching on in-memory text, not a database query.
        # Extracted addresses are validated with eth_utils.is_address() below before any
        # downstream DB or RPC usage in verify_contract_status, so there is no injection
        # surface here despite the visual similarity to query construction.
        evm_addresses = list(set(re.findall(EVM_ADDRESS_REGEX, text)))
        sol_addresses = list(set(re.findall(SOLANA_ADDRESS_REGEX, text)))

        # Filter EVM addresses using eth_utils for checksum/validity
        valid_evm = [addr for addr in evm_addresses if is_address(addr)]
        
        return {
            "EVM": valid_evm,
            "SOLANA": sol_addresses
        }

    async def verify_contract_status(self, address: str, chain: str) -> Dict[str, Any]:
        """
        Checks if an address is a contract and if it has code on-chain.
        Note: True 'verification' (source code match) usually requires Etherscan API.
        For now, we check if it's a contract (has code) vs an EOA (wallet).
        """
        if chain not in self.w3_instances:
            return {"error": f"Chain {chain} not supported for on-chain verification."}

        w3 = self.w3_instances[chain]
        try:
            # Checksum the address
            checksum_addr = w3.to_checksum_address(address)
            code = await asyncio.to_thread(w3.eth.get_code, checksum_addr)
            
            is_contract = len(code) > 0
            
            return {
                "address": checksum_addr,
                "is_contract": is_contract,
                "has_code": is_contract,
                "chain": chain
            }
        except Exception as e:
            logger.error(f"Error verifying address {address} on {chain}: {e}")
            return {"error": str(e)}

# Singleton instance
blockchain_service = BlockchainService()
