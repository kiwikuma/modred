
from fieldoperations import FieldOperations
from pod import POD
import numpy as N
import util

# Derived class
class DMD(object):
    """
    Dynamic Mode Decomposition/Koopman Mode Decomposition
        
    Generate Ritz vectors from simulation snapshots. Uses POD and FieldOperations
    instances for low-level parallel processing.    
    """

    def __init__(self, load_field=None, save_field=None, load_mat=util.\
        load_mat_text, save_mat=util.save_mat_text, inner_product=None, 
        maxFields=None, pod=None, verbose=True):
        """
        DMD constructor
        """
        self.fieldOperations = FieldOperations(load_field=load_field,\
            save_field=save_field, inner_product=inner_product,
            maxFields=maxFields, verbose=\
            verbose)

        self.load_mat = load_mat
        self.save_mat = save_mat
        self.pod = pod
        self.verbose = verbose

    def load_decomp(self, ritzValsPath, modeNormsPath, buildCoeffPath):
        """
        Loads the decomposition matrices from file. 
        """
        if self.load_mat is None:
            raise UndefinedError('Must specify a load_mat function')
        self.ritzVals = N.squeeze(N.array(self.load_mat(ritzValsPath)))
        self.modeNorms = N.squeeze(N.array(self.load_mat(modeNormsPath)))
        self.buildCoeff = self.load_mat(buildCoeffPath)
            
    def save_decomp(self, ritzValsPath, modeNormsPath, buildCoeffPath):
        """Save the decomposition matrices to file."""
        if self.save_mat is None:
            raise util.UndefinedError("save_mat is undefined, can't save")
            
        self.save_mat(self.ritzVals, ritzValsPath)
        self.save_mat(self.modeNorms, modeNormsPath)
        self.save_mat(self.buildCoeff, buildCoeffPath)

    def compute_decomp(self, snapPaths, sharedMemLoad=True, 
        sharedMemInnerProduct=True):
        """
        Compute DMD decomposition
        """
         
        if snapPaths is not None:
            self.snapPaths = snapPaths
        if self.snapPaths is None:
            raise util.UndefinedError('snapPaths is not given')

        # Compute POD from snapshots (excluding last snapshot)
        if self.pod is None:
            self.pod = POD(load_field=self.fieldOperations.load_field, 
                inner_product=self.fieldOperations.inner_product, 
                maxFields=self.fieldOperations.maxFields, 
                verbose=self.verbose)
            self.pod.compute_decomp(snapPaths=self.snapPaths[:-1], 
                sharedMemLoad=sharedMemLoad, sharedMemInnerProduct=\
                sharedMemInnerProduct)
        elif self.snapPaths[:-1] != self.pod.snapPaths or len(snapPaths) !=\
            len(self.pod.snapPaths)+1:
            raise RuntimeError('Snapshot mistmatch between POD and DMD '+\
                'objects.')     
        _podSingValsSqrtMat = N.mat(N.diag(N.array(self.pod.singVals).\
            squeeze() ** -0.5))

        # Inner product of snapshots w/POD modes
        numSnaps = len(self.snapPaths)
        podModesStarTimesSnaps = N.mat(N.empty((numSnaps-1, numSnaps-1)))
        podModesStarTimesSnaps[:, :-1] = self.pod.correlationMat[:,1:]  
        podModesStarTimesSnaps[:, -1] = self.fieldOperations.\
            compute_inner_product_mat(self.snapPaths[:-1], self.snapPaths[
            -1], sharedMemLoad=sharedMemLoad, sharedMemInnerProduct=\
            sharedMemInnerProduct)
        podModesStarTimesSnaps = _podSingValsSqrtMat * self.pod.\
            singVecs.H * podModesStarTimesSnaps
            
        # Reduced order linear system
        lowOrderLinearMap = podModesStarTimesSnaps * self.pod.singVecs * \
            _podSingValsSqrtMat
        self.ritzVals, lowOrderEigVecs = N.linalg.eig(lowOrderLinearMap)
        
        # Scale Ritz vectors
        ritzVecsStarTimesInitSnap = lowOrderEigVecs.H * _podSingValsSqrtMat * \
            self.pod.singVecs.H * self.pod.correlationMat[:,0]
        ritzVecScaling = N.linalg.inv(lowOrderEigVecs.H * lowOrderEigVecs) *\
            ritzVecsStarTimesInitSnap
        ritzVecScaling = N.mat(N.diag(N.array(ritzVecScaling).squeeze()))

        # Compute mode energies
        self.buildCoeff = self.pod.singVecs * _podSingValsSqrtMat *\
            lowOrderEigVecs * ritzVecScaling
        self.modeNorms = N.diag(self.buildCoeff.H * self.pod.\
            correlationMat * self.buildCoeff).real
        
    def compute_modes(self, modeNumList, modePath, indexFrom=1, snapPaths=None,
        sharedMemLoad=True, sharedMemSave=True):
        if self.buildCoeff is None:
            raise util.UndefinedError('Must define self.buildCoeff')
        # User should specify ALL snapshots, even though all but last are used
        if snapPaths is not None:
            self.snapPaths = snapPaths
        self.fieldOperations._compute_modes(modeNumList, modePath, self.\
            snapPaths[:-1], self.buildCoeff, indexFrom=indexFrom, 
            sharedMemLoad=sharedMemLoad, sharedMemSave=sharedMemSave)

        
        
             
