from __future__ import annotations
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler
from ..physics import pairing_sign

class SEMFResidualGP:
    model_id="ZME-SEMF-GP-RESIDUAL-v1"
    def __init__(self, semf, random_seed=0):
        self.semf=semf; self.random_seed=random_seed; self.scaler=StandardScaler()
        kernel=ConstantKernel(1.0,(1e-3,1e3))*RBF(length_scale=np.ones(5),length_scale_bounds=(1e-2,1e3))+WhiteKernel(1.0,(1e-6,1e4))
        self.gp=GaussianProcessRegressor(kernel=kernel,normalize_y=True,random_state=random_seed,n_restarts_optimizer=0)
    @staticmethod
    def features(Z,N):
        A=Z+N
        return [Z,N,A,(N-Z)/A,pairing_sign(Z,N)]
    def fit(self, records):
        X=np.array([self.features(r.Z,r.N) for r in records],float)
        y=np.array([r.mass_excess_keV-self.semf.predict_mass_excess(r.Z,r.N) for r in records],float)
        Xs=self.scaler.fit_transform(X)
        self.gp.fit(Xs,y)
        return self
    def predict(self,Z,N):
        x=self.scaler.transform(np.array([self.features(Z,N)],float))
        mean,std=self.gp.predict(x,return_std=True)
        return self.semf.predict_mass_excess(Z,N)+float(mean[0]),float(std[0])
    def manifest(self):
        return {"model_id":self.model_id,"kernel":str(self.gp.kernel_),"random_seed":self.random_seed,
                "scaler_mean":[float(x) for x in self.scaler.mean_],"scaler_scale":[float(x) for x in self.scaler.scale_],
                "parent":self.semf.manifest()}
