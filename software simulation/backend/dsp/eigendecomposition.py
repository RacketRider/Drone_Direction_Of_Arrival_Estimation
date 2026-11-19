"""
Hermitian Eigenvalue Decomposition (EVD) and Subspace Partitioning.
Computes sorted eigenvalues, eigenvectors, and the noise subspace projection operator.
"""

from typing import Tuple
import numpy as np

class SubspaceDecomposition:
    """Performs Hermitian EVD and partitions signal vs noise subspaces."""

    @staticmethod
    def decompose(
        r_xx: np.ndarray,
        num_sources: int = 1
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Decomposes R_xx into sorted eigenvalues and orthonormal eigenvectors.
        
        Args:
            r_xx: Complex Hermitian covariance matrix [M, M]
            num_sources: Assumed number of active incident sources (default 1)
            
        Returns:
            eigenvalues: Real array of sorted eigenvalues [M] descending
            eigenvectors: Complex unitary matrix [M, M] sorted descending
            noise_subspace: Matrix E_n [M, M - num_sources]
            noise_projector: Projection operator P_n = E_n * E_n^H [M, M]
        """
        # np.linalg.eigh computes eigenvalues in ascending order for Hermitian input
        eigvals, eigvecs = np.linalg.eigh(r_xx)

        # Sort descending: lambda_1 >= lambda_2 >= ... >= lambda_M
        desc_indices = np.argsort(eigvals)[::-1]
        sorted_eigvals = np.real(eigvals[desc_indices])
        sorted_eigvecs = eigvecs[:, desc_indices]

        # Partition into signal subspace E_s and noise subspace E_n
        e_noise = sorted_eigvecs[:, num_sources:]  # Shape: [M, M - num_sources]

        # Projection operator onto noise subspace: P_n = E_n * E_n^H
        p_noise = e_noise @ e_noise.conj().T

        return sorted_eigvals, sorted_eigvecs, e_noise, p_noise

