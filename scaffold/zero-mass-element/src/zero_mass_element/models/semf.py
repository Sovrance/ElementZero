from __future__ import annotations
import numpy as np
from ..physics import mass_excess_to_binding_mev, binding_to_mass_excess_kev, pairing_sign

class SEMFModel:
    model_id="ZME-SEMF-LS-v1"
    def __init__(self): self.coef_=None
    @staticmethod
    def design(Z,N):
        A=Z+N
        return np.array([A, -A**(2/3), -Z*(Z-1)/A**(1/3), -(N-Z)**2/A, pairing_sign(Z,N)/np.sqrt(A)],float)
    def fit(self, records):
        X=np.vstack([self.design(r.Z,r.N) for r in records])
        y=np.array([mass_excess_to_binding_mev(r.Z,r.N,r.mass_excess_keV) for r in records])
        self.coef_, *_=np.linalg.lstsq(X,y,rcond=None)
        return self
    def predict_mass_excess(self, Z,N):
        if self.coef_ is None: raise RuntimeError("model not fit")
        B=float(self.design(Z,N)@self.coef_)
        return binding_to_mass_excess_kev(Z,N,B)
    def manifest(self):
        return {"model_id":self.model_id,"coefficients":[float(x) for x in self.coef_],"fit":"numpy.linalg.lstsq"}
