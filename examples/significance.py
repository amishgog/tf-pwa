#!/usr/bin/env python3
import sys
import os.path
this_dir = os.path.dirname(__file__)
sys.path.insert(0, this_dir + '/..')

from tf_pwa.model import Cache_Model,param_list,FCN
import tensorflow as tf
import time
import numpy as np
import json
from scipy.optimize import minimize,BFGS,basinhopping
from tf_pwa.angle import cal_ang_file,cal_ang_file4
from tf_pwa.utils import load_config_file,flatten_np_data,pprint,error_print,std_polar

import math
from tf_pwa.significance import significance
import functools

mode = "3"
if mode=="4":
  from tf_pwa.amplitude4 import AllAmplitude4 as AllAmplitude,param_list
else:
  from tf_pwa.amplitude import AllAmplitude,param_list

from tf_pwa.applications import fit_scipy


def prepare_data(dtype="float64",model="3"):
  fname = [["./data/data4600_new.dat","data/Dst0_data4600_new.dat"],
       ["./data/bg4600_new.dat","data/Dst0_bg4600_new.dat"],
       ["./data/PHSP4600_new.dat","data/Dst0_PHSP4600_new.dat"]
  ]
  tname = ["data","bg","PHSP"]
  data_np = {}
  for i in range(len(tname)):
    if model == "3" :
      data_np[tname[i]] = cal_ang_file(fname[i][0],dtype)
    elif model == "4":
      data_np[tname[i]] = cal_ang_file4(fname[i][0],fname[i][1],dtype)
  def load_data(name):
    dat = []
    tmp = flatten_np_data(data_np[name])
    for i in param_list:
      tmp_data = tf.Variable(tmp[i],name=i,dtype=dtype)
      dat.append(tmp_data)
    return dat
  #with tf.device('/device:GPU:0'):
  data = load_data("data")
  bg = load_data("bg")
  mcdata = load_data("PHSP")
  return data, bg, mcdata

def cal_significance(config_list,delta_res=None,method="-",prefix=""):
  POLAR = True 
  dtype = "float64"
  w_bkg = 0.768331
  #set_gpu_mem_growth()
  #tf.keras.backend.set_floatx(dtype)
  # open Resonances list as dict 
  
  data, bg, mcdata = prepare_data(dtype=dtype,model=mode)
  curves = {}
  sigmas = {}
  base_config_list = config_list.copy()
  if method == "-":
    if delta_res is None:
      delta_res = [[i] for i in config_list]
    delta_config = {}
    for i in delta_res:
      tmp = config_list.copy()
      for j in i:
        tmp.pop(j) # pop的参数应该是个int吧？？？
      if len(i)==1:
        delta_config[i[0]] = tmp
      else:
        name = functools.reduce(lambda x,y:x+"+"+y,i) # "D+Dp+Dm"
        delta_config[name] = tmp
  elif method == "+":
    if delta_res is None:
      raise Exception("for method `+` delta_res is required!")
    delta_config = {}
    for i in delta_res:
      for j in i:
        if j in base_config_list:
          base_config_list.pop(j)
    for i in delta_res:
      tmp = base_config_list.copy()
      for j in i:
        tmp[j] = config_list[j]
      if len(i)==1:
        delta_config[i[0]] = tmp
      else:
        name = functools.reduce(lambda x,y:x+"+"+y,i)
        delta_config[name] = tmp
  
  print("########## base fit")
  base_fit,val,curve = fit(base_config_list,w_bkg,data,mcdata,bg)
  print("########## base FCN",base_fit.fun)
  curves["all"] = curve
  n_all = len(base_fit.x) # number of fitting parameters
  for i in delta_config:
    print("########## fit",i)
    sig_fit,val,curve = fit(delta_config[i],w_bkg,data,mcdata,bg)
    curves[i] = curve
    sigma = significance(base_fit.fun,sig_fit.fun,abs(n_all-len(sig_fit.x)))
    print("########## FCN",i,"=",sig_fit.fun)
    print("########## significance of",i,":",sigma)
    sigmas[i] = sigma
    
  print("########## significance")
  pprint(sigmas)
  
  with open(prefix+"significance_curve.json","w") as f:
    json.dump(curves,f,indent=2)
  with open(prefix+"significance.json","w") as f:
    json.dump(sigmas,f,indent=2)
  
  
def fit(config_list,w_bkg,data,mcdata,bg=None,init_params={},batch=65000,niter=10):
  
  amp = AllAmplitude(config_list)
  a = Cache_Model(amp,w_bkg,data,mcdata,bg=bg,batch=batch)
  a.set_params(init_params)
  # fit configure
  args = {}
  args_name = []
  x0 = []
  bnds = []
  bounds_dict = {
      "Zc_4160_m0:0":(4.1,4.25),
      "Zc_4160_g0:0":(0,None)
  }
  
  for i in a.Amp.trainable_variables:
    args[i.name] = i.numpy()
    x0.append(i.numpy())
    args_name.append(i.name)
    if i.name in bounds_dict:
      bnds.append(bounds_dict[i.name])
    else:
      bnds.append((None,None))
    args["error_"+i.name] = 0.1
  
  pprint(a.get_params())
  #print(data,bg,mcdata)
  #t = time.time()
  #nll,g = a.cal_nll_gradient()#data_w,mcdata,weight=weights,batch=50000)
  #print("nll:",nll,"Time:",time.time()-t)
  #exit()

  print("########## chain decay:")
  for i in a.Amp.A.chain_decay():
    print(i,flush=True)
  now = time.time()

  s, nlls, points = fit_scipy(a,method="basinhopping",bounds_dict=bounds_dict,niter=niter)
  print("########## fit state:")
  print(s)
  print("\nTime for fitting:",time.time()-now)
  
  val = dict(zip(args_name,a.Amp.get_all_val()))
  pprint(val)
  if "Zc_4160" in config_list:  # 为什么Zc4160又算一遍？浮动mg？
    if "float" in config_list["Zc_4160"]:
      if config_list["Zc_4160"]["float"] == False:
        config_list["Zc_4160"]["float"] = True
        s,val,tmp = fit(config_list,w_bkg,data,mcdata,bg=bg,init_params=val,batch=batch,niter=0)
        return s,val,{"nlls":nlls + tmp["nlls"],"points":points+tmp["points"]}  #mg浮动不浮动的轨迹接上
  return s,val,{"nlls":nlls,"points":points}


def main():
  config_list = load_config_file("Resonances")
  delta_res = [["Zc_4160"],["D2_2460","D2_2460p"]]
  cal_significance(config_list,delta_res,method="+")

if __name__ == "__main__":
  main()
