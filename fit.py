#!/usr/bin/env python3
from tf_pwa.config_loader import ConfigLoader, MultiConfig
from pprint import pprint
from tf_pwa.utils import error_print
import tensorflow as tf

def fit(config_file="config.yml", init_params="init_params.json", method="BFGS"):

    config = ConfigLoader(config_file)
    try:
        config.set_params(init_params)
        print("using {}".format(init_params))
    except Exception as e:
        print("using RANDOM parameters")
    
    print("\n########### initial parameters")
    pprint(config.get_params())

    data, phsp, bg = config.get_all_data()
    
    fit_result = config.fit(data, phsp, bg=bg, batch=65000, method=method)
    
    pprint(fit_result.params)
    fit_result.save_as("final_params.json")
    config.plot_partial_wave(fit_result, data, phsp, bg=bg, plot_delta=True)
    fit_error = config.get_params_error(fit_result, data, phsp, bg=bg, batch=13000)
    fit_result.set_error(fit_error)
    pprint(fit_error)
    
    print("\n########## fit results:")
    for k, v in config.get_params().items():
        print(k, error_print(v, fit_error.get(k, None)))
    
    fit_frac, err_frac = config.cal_fitfractions({}, phsp)
    print("########## fit fractions")
    for i in fit_frac:
        print(i, error_print(fit_frac[i], err_frac.get(i, None)))


def fit_combine(config_file=["config.yml"], init_params="init_params.json"):

    config = MultiConfig(config_file)
    try:
        config.set_params(init_params)
        print("using {}".format(init_params))
    except Exception as e:
        print("using RANDOM parameters")
    
    print("\n########### initial parameters")
    pprint(config.get_params())
    
    fit_result = config.fit(batch=65000)
    
    pprint(fit_result.params)
    fit_result.save_as("final_params.json")
    for i, c in enumerate(config.configs):
        c.plot_partial_wave(fit_result, prefix="figure/s{}_".format(i))

    fit_error = config.get_params_error(fit_result, batch=13000)
    fit_result.set_error(fit_error)
    pprint(fit_error)
    
    print("\n########## fit results:")
    for k, v in fit_result.params.items():
        print(k, error_print(v, fit_error.get(k, None)))



def main():
    import argparse
    parser = argparse.ArgumentParser(description="simple fit scripts")
    parser.add_argument("--no-GPU", action="store_false", default=True, dest="has_gpu")
    parser.add_argument("--config", default="config.yml", dest="config")
    parser.add_argument("--init_params", default="init_params.json", dest="init")
    parser.add_argument("--method", default="BFGS", dest="method")
    results = parser.parse_args()
    config = results.config.split(",")
    if results.has_gpu:
        devices = "/device:GPU:0"
    else:
        devices = "/device:CPU:0"
    with tf.device(devices):
        if len(config) > 1:
            fit_combine(config, results.init)
        else:
            fit(results.config, results.init, results.method)


if __name__ == "__main__":
    main()
