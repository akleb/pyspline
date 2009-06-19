#!/usr/local/bin/python
'''
pySpline

Contains an relatively thin interface to the cmlib spline functions

Copyright (c) 2009 by G. Kenway
All rights reserved. Not to be used for commercial purposes.
Revision: 1.0   $Date: 24/05/2009$


Developers:
-----------
- Gaetan Kenway (GKK)

History
-------
	v. 1.0 - Initial Class Creation (GKK, 2009)
'''

__version__ = '$Revision: $'


# =============================================================================
# Standard Python modules
# =============================================================================
import os, sys, string, time
print 'sys.path',sys.path
# =============================================================================
# External Python modules
# =============================================================================
from numpy import linspace, cos, pi, hstack, zeros, ones, sqrt, imag, interp, \
    array, real, reshape, meshgrid, dot, cross

import scipy.linalg
from pyOpt_optimization import Optimization
from pySNOPT import SNOPT
import pyspline
import pyspline_cs

# =============================================================================
# pySpline class
# =============================================================================

class spline():

    def __init__(self,Nsurf,u,v,X,fit_type='lms',Nctlu = 13, Nctlv = 9, ku=4,kv=4,*args, **kwargs):
        print 'fit_type:',fit_type

        self.Nsurf = Nsurf
        self.u0 = u
        self.v0 = v        
        self.x0 = X
        self.Nctlu = Nctlu
        self.Nctlv = Nctlv
        self.ku = ku
        self.kv = kv

        if fit_type == 'interpolate':
            self.Nctlu = len(u[0])
            self.Nctlv = len(v[0])
            self.Nu = len(u[0])
            self.Nv = len(v[0])
            self.coef = zeros([Nsurf,self.Nctlu,self.Nctlv,3])
            for isurf in xrange(Nsurf):
                for idim in xrange(3):
                    self.tu,self.tv,self.coef[isurf,:,:,idim] = pyspline.b2ink(u[isurf,:],v[isurf,:],X[isurf,:,:,idim],ku,kv)
                # end for
            # end for

           
        elif fit_type == 'lms':
            Nu = len(u[0,:])
            Nv = len(v[0,:])
            self.Nu = Nu
            self.Nv = Nv
            # ==============================
            # Find the Initial Knot Vectors
            # ==============================

            # U knots

            tu0= zeros(Nctlu + ku)
            tu0[ku-1:Nctlu+1]  = 0.5*(1-cos(linspace(0,pi,Nctlu-ku+2)))
            tu0[0:ku] = 0
            tu0[Nctlu:Nctlu+ku] = 1.0#+0.1*(tu0[Nctlu]-tu0[Nctlu-1])
            
            # V Knots
            
            tv0= zeros(Nctlv + kv)
            tv0[kv-1:Nctlv+1]=  linspace(0,1,Nctlv-kv+2)
            # tv0[kv-1:Nctlv+1]  = 0.5*(1-cos(linspace(0,pi,Nctlv-kv+2)))
            tv0[0:kv] = 0
            tv0[Nctlv:Nctlv+kv] = 1.0#+0.1*(tv0[Nctlv]-tv0[Nctlv-1])

            self.tu = tu0
            self.tv = tv0

            # Calculate the jacobian J, for fixed t and s

            h = 1.0e-40j
            self.J = zeros([Nsurf,Nu*Nv,Nctlu*Nctlv])
            ctl = zeros([Nctlu,Nctlv],'D')
            
            V = zeros((Nsurf,Nu,Nv))
            U = zeros((Nsurf,Nu,Nv))
            
            for isurf in xrange(Nsurf):
                [V[isurf], U[isurf]] = meshgrid(v[isurf,:],u[isurf,:])
                for j in xrange(Nctlv):
                    for i in xrange(Nctlu):
                        ctl[i,j] += h
                        val = pyspline_cs.b2valv(U[isurf].flatten(),V[isurf].flatten(),0,0,tu0,tv0,ku,kv,ctl)
                        ctl[i,j] -= h    
                        self.J[isurf,:,i*Nctlv + j] = imag(val)/imag(h)
                    # end for
                # end for 
            # end for

            # =============================================================================
            #  Run Optimization Problem
            # =============================================================================

            opt_prob = Optimization('Cubic Spline Optimization Problem',self.__objcon)

            # ===================
            #  Constraints
            # ===================

            # First figure out how many constraints we are going to have
            ncon = 0
            ndv = Nctlu*Nctlv*Nsurf*3
            # Each of four corners on each Surf

            ncon += 4*Nsurf*3 # three for the dimensions
            ncon += 2*Nctlv*3 # Set the LE and TE to be same on upper and lower surfaces
            ncon += Nctlv*3   # 3*Nctlv constraint for the continutity constraint

            self.Bcon = zeros([ncon,ndv]) #This is the constraint derivative matrix ((Mostly) constant)

            # Corner Constraints
            counter = 0
            for isurf in xrange(Nsurf):
                for idim in xrange(3):
                    opt_prob.addCon('coner constr',type= 'i',lower=X[isurf,0,0,idim],upper=X[isurf,0,0,idim])
                    opt_prob.addCon('coner constr',type= 'i',lower=X[isurf,0,-1,idim],upper=X[isurf,0,-1,idim])
                    opt_prob.addCon('coner constr',type= 'i',lower=X[isurf,-1,0,idim],upper=X[isurf,-1,0,idim])
                    opt_prob.addCon('coner constr',type= 'i',lower=X[isurf,-1,-1,idim],upper=X[isurf,-1,-1,idim])

                    self.Bcon[counter  ,isurf*3*Nctlu*Nctlv + idim*Nctlu*Nctlv + 0] = 1
                    self.Bcon[counter+1,isurf*3*Nctlu*Nctlv + idim*Nctlu*Nctlv + Nctlv-1] = 1
                    self.Bcon[counter+2,isurf*3*Nctlu*Nctlv + idim*Nctlu*Nctlv + Nctlu*Nctlv-Nctlv] = 1
                    self.Bcon[counter+3,isurf*3*Nctlu*Nctlv + idim*Nctlu*Nctlv + Nctlu*Nctlv-1] = 1
                    counter += 4
                # end for
            # end for 

            # Edge Constraints
            for idim in xrange(3):
                for j in xrange(Nctlv):
                    opt_prob.addCon('edge constraint',type='i',lower=0,upper=0)
                    opt_prob.addCon('edge constraint',type='i',lower=0,upper=0)
                    self.Bcon[counter,idim*Nctlv*Nctlu + j] = 1
                    self.Bcon[counter,3*Nctlu*Nctlv + idim*Nctlv*Nctlu + (Nctlu-1)*Nctlv + j] = -1
                    self.Bcon[counter+1,idim*Nctlv*Nctlu + (Nctlu-1)*Nctlv + j] = 1
                    self.Bcon[counter+1,3*Nctlu*Nctlv + idim*Nctlv*Nctlu + j] = -1
                    counter +=2
                # end for
            # end for

            # LE Continutiy Constraint
            for j in xrange(Nctlv):
                for icon in xrange(3):
                    opt_prob.addCon('LE constraint',type='i',lower=0,upper=0)
                # end for
            #end for

            # ===================
            #  Variables
            # ===================

            # Lets do a lms 

            timeA = time.time()
            ctl = pyspline.fit_surf(Nsurf,Nu,Nv,Nctlu,Nctlv,ncon,self.J,X,self.Bcon,zeros(ncon))
            print 'LMS Fit Time:',time.time()-timeA
            for isurf in xrange(Nsurf):
                for idim in xrange(3):
                    if idim == 0: name = 'ctlx'
                    if idim == 1: name = 'ctly'
                    if idim == 2: name = 'ctlz'
                    name +=str(isurf)
                    opt_prob.addVarGroup(name,Nctlu*Nctlv,'c',value=ctl[isurf,:,:,idim].flatten(),\
                                             lower=ctl[isurf,:,:,idim].flatten()-.1, \
                                             upper=ctl[isurf,:,:,idim].flatten()+.1)
                # end for
            # end for 

            # ===================
            #  Objective
            # ===================
            opt_prob.addObj('RMSerror')
            opt = SNOPT()

            # ===================
            #  SNOPT Options
            # ===================
            #opt.setOption('Derivative level',0)
            #opt.setOption('Verify level',3)
            opt.setOption('Major iterations limit',150)
            #opt.setOption('Linesearch tolerance',.1)
            #opt.setOption('Nonderivative linesearch')
            opt.setOption('Major optimality tolerance', 1e-6)
            opt.setOption('Major feasibility tolerance',1e-9)
            opt.setOption('Minor feasibility tolerance',1e-6)

            # ===================
            #  Run Optimization
            # ===================

            result = opt(opt_prob,self.__sens)

            print '#--------------------------------'
            print '# RMS Error: ',sqrt(result[0][0]/(2*Nu*Nv))
            print '#--------------------------------'
            
            # Set the control points
            self.coef = self.__unpack_x(result[1][:])

        else:
            print 'Error: fit_type is not understood. Type must be \'lms\' or \'interpolate\''
            sys.exit(0)
        return

    def __objcon(self,x):
        '''Get the rms error for the given set of design variables'''
        # Unpack the x-values
        Bcon  = self.Bcon
        ctl = self.__unpack_x(x)

        total = 0.0

        for isurf in xrange(self.Nsurf):
            for idim in xrange(3):
                total += sum((dot(self.J[isurf],ctl[isurf,:,:,idim].flatten()) - self.x0[isurf,:,:,idim].flatten())**2)
            # end for
        # end for 
        fcon = dot(Bcon,x)
        index = 4*self.Nsurf*3 + 2*self.Nctlv*3

       #  # Calculate the LE constraint
        for j in xrange(self.Nctlv):

            A = ctl[0,0,j,:] # Root LE (upper)
            B = ctl[0,1,j,:] # Root LE upper +1
            C = ctl[1,-2,j,:]# Root LE lower +1

            # Area = 0.5*abs( xA*yC - xAyB + xByA - xByC + xCyB - xCyA )

            A1 = A[0]*C[1] - A[0]*B[1] + B[0]*A[1] -B[0]*C[1] + C[0]*B[1] - C[0]*A[1]
            A2 = A[1]*C[2] - A[1]*B[2] + B[1]*A[2] -B[1]*C[2] + C[1]*B[2] - C[1]*A[2]
            A3 = A[0]*C[2] - A[0]*B[2] + B[0]*A[2] -B[0]*C[2] + C[0]*B[2] - C[0]*A[2]

            fcon[index:index+3] = array([A1,A2,A3])
            index += 3
        # end for

        return total,fcon,False


    def __sens(self,x,f_obj,f_con):

        ndv = len(x)
        g_obj = zeros(ndv)
         # Unpack the x-values
        N = self.Nctlu*self.Nctlv

        ctl = self.__unpack_x(x)

        for isurf in xrange(self.Nsurf):
            for idim in xrange(3):
                g_obj[isurf*3*N + idim*N : isurf*3*N + idim*N + N] = \
                    2*dot(dot(self.J[isurf],ctl[isurf,:,:,idim].flatten())-self.x0[isurf,:,:,idim].flatten(),self.J[isurf])
            # end for
        # end for 

        g_con = self.Bcon
        h = 1.0e-40j
        x = array(x,'D')

        for i in xrange(ndv):
            index = 4*self.Nsurf*3 + 2*self.Nctlv*3
            x[i] += h
            ctl = self.__unpack_x_complex(x)
            for j in xrange(self.Nctlv):
                A = ctl[0,0,j,:] # Root LE (upper)
                B = ctl[0,1,j,:] # Root LE upper +1
                C = ctl[1,-2,j,:]# Root LE lower +1

                # Area = 0.5*abs( xA*yC - xAyB + xByA - xByC + xCyB - xCyA )

                A1 = A[0]*C[1] - A[0]*B[1] + B[0]*A[1] -B[0]*C[1] + C[0]*B[1] - C[0]*A[1]
                A2 = A[1]*C[2] - A[1]*B[2] + B[1]*A[2] -B[1]*C[2] + C[1]*B[2] - C[1]*A[2]
                A3 = A[0]*C[2] - A[0]*B[2] + B[0]*A[2] -B[0]*C[2] + C[0]*B[2] - C[0]*A[2]

                g_con[index:index+3,i] = imag(array([A1,A2,A3]))/imag(h)
                index += 3
            # end for
            x[i] -= h
        # end for
        return g_obj,g_con,False

    def __unpack_x(self,x):
        ctl = zeros((self.Nsurf,self.Nctlu,self.Nctlv,3))
        N = self.Nctlu*self.Nctlv
        for isurf in xrange(self.Nsurf):
            for idim in xrange(3):
                ctl[isurf,:,:,idim] = reshape(x[isurf*3*N + idim*N : isurf*3*N + idim*N + N],[self.Nctlu,self.Nctlv])
            # end if
        #end if
        return ctl

    def __unpack_x_complex(self,x):
        ctl = zeros((self.Nsurf,self.Nctlu,self.Nctlv,3),'D')
        N = self.Nctlu*self.Nctlv
        for isurf in xrange(self.Nsurf):
            for idim in xrange(3):
                ctl[isurf,:,:,idim] = reshape(x[isurf*3*N + idim*N : isurf*3*N + idim*N + N],[self.Nctlu,self.Nctlv])
            # end if
        #end if
        return ctl


    def getValue(self,isurf,u,v):
        
        '''Get the value of the spline at point u,v'''
        x = zeros([3])
        for idim in xrange(3):
            x[idim] = pyspline.b2val(u,v,0,0,self.tu,self.tv,self.ku,self.kv,self.coef[isurf,:,:,idim])
        
        return x


    def getValueV(self,isurf,u,v):
        '''Get the value of a spline at vector of points u,v'''
        assert u.shape == v.shape, 'u and v must be the same length'
        x = zeros(len(u),3)
        for idim in xrange(3):
            x[:,idim] = pyspline.b2valv(u,v,0,0,self.tu,self.tv,self.ku,self.kv,self.coef[isurf,:,:,idim])
        return x

    def getValueM(self,isurf,u,v):
        '''Get the value of a spline at matrix of points u,v'''
        assert u.shape == v.shape, 'u and v must be the same shape'
        x = zeros((u.shape[0],u.shape[1],3))
        for idim in xrange(3):
            x[:,:,idim] = pyspline.b2valm(u,v,0,0,self.tu,self.tv,self.ku,self.kv,self.coef[isurf,:,:,idim])

        return x

    def getJacobian(self,isurf,u,v):
        
        '''Get the jacobian at point u,v'''

        J = zeros((3,2))
        
        for idim in xrange(3):
            J[idim,0] = pyspline.b2val(u,v,1,0,self.tu,self.tv,self.ku,self.kv,self.coef[isurf,:,:,idim])
            J[idim,1] = pyspline.b2val(u,v,0,1,self.tu,self.tv,self.ku,self.kv,self.bcoef_x)

        return J

    def findUV(self,isurf,x0,r,u0,v0):
        ''' Try to find the parametric u-v coordinate of the spline
        which coorsponds to the intersection of the directed vector 
        v = x0 + r*s where x0 is a basepoint, r  is a direction vector
        and s is the distance along the vector.
        
        If possible, both intersections are attempted with the first 
        coorsponding to the first intersection in the direction of r
        
        Input: 
        
        x0: array, length 3: The base of the vector
        r : array, length 3: The direction of the vector

        u0: scalar: The guess for the u coordinate of the intersection
        v0: scalar: The guess for the v coordinate of the intersection

        '''

        maxIter = 25

        u = u0
        v = v0
        s = 0 #Start at the basepoint

        for iter in xrange(maxIter):

            #just in case, force crop u,v to [-1,1]
            if u<-1: u = -1
            if u>1 : u =  1
            if v<-1: v = -1
            if v>1 : v =  1

            x = self.getValue(isurf,u,v) #x contains the x,y,z coordinates 

            f = mat(zeros((3,1)))
            f[0] = x[0]-(x0[0]+r[0]*s)
            f[1] = x[1]-(x0[1]+r[1]*s)
            f[2] = x[2]-(x0[2]+r[2]*s)

            J = self.getJacobian(isurf,u,v)
            A = mat(zeros((3,3)))
            A[:,0:2] = J
            A[0,2]   = -r[0]
            A[1,2]   = -r[1]
            A[2,2]   = -r[2]

            x_up = scipy.linalg.solve(A,-f)

            # Add a little error checking here:
            
            if u + x_up[0] < -1 or u + x_up[0] > 1 or \
               v + x_up[1] < -1 or v + x_up[1] > 1:
                #Cut the size of the step in 1/2
                x_up /= 2

            u = u + x_up[0]
            v = v + x_up[1]
            s = s + x_up[2]

            if scipy.linalg.norm(x_up) < 1e-12:
                return u,v,x

        # end for

        print 'Warning: Newton Iteration for u,v,s did not converge:'
        print 'u = %f, v = %f, s = %f\n'%(u,v,s)
        print 'Norm of update:',scipy.linalg.norm(x_up)

        return u,v,x

    def writeTecplot(self,file_name):
        
        f = open(file_name,'w')
        for isurf in xrange(self.Nsurf):
            f.write ('VARIABLES = "X", "Y","Z"\n')
            f.write('Zone T=%s I=%d J = %d\n'%('orig_data',self.Nu,self.Nv))
            f.write('DATAPACKING=POINT\n')
            for j in xrange(self.Nv):
                for i in xrange(self.Nu):
                    f.write('%f %f %f \n'%(self.x0[isurf,i,j,0],self.x0[isurf,i,j,1],self.x0[isurf,i,j,2]))
                # end for
            # end for
        # end for 

        # Dump re-interpolated surface
        for isurf in xrange(self.Nsurf):
            f.write('Zone T=%s I=%d J = %d\n'%('interpolated',self.Nu,self.Nv))
            f.write('DATAPACKING=POINT\n')
            for j in xrange(self.Nv):
                for i in xrange(self.Nu):
                    for idim in xrange(3):
                        f.write('%f '%(pyspline.b2val(self.u0[isurf,i],self.v0[isurf,j],0,0,self.tu,self.tv,self.ku,self.kv,self.coef[isurf,:,:,idim])))
                    # end for 
                    f.write('\n')
                # end for
            # end for
        # end for 

        # Dump Control Points
        for isurf in xrange(self.Nsurf):
            f.write('Zone T=%s I=%d J = %d\n'%('control_pts',self.Nctlu,self.Nctlv))
            f.write('DATAPACKING=POINT\n')
            for j in xrange(self.Nctlv):
                for i in xrange(self.Nctlu):
                    f.write('%f %f %f \n'%(self.coef[isurf,i,j,0],self.coef[isurf,i,j,1],self.coef[isurf,i,j,2]))
                # end for
            # end for
        # end for 

#==============================================================================
# Class Test
#==============================================================================
if __name__ == '__main__':
	
    # Run a Simple Test Case
    print 'Testing pySpline...\n'
    print 'There is an example in the ./example directory'




