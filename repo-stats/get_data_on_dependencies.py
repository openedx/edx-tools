#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import json
import os
import re
import pdb
from subprocess import check_output
from email.parser import BytesHeaderParser
import email
import pandas as pd

from tqdm import tqdm
import pprint
import argparse

pp = pprint.PrettyPrinter(indent=4)

"""
Python script to output output state of each dependecy for a repo.

Currently only gets data from pip show for each dependency and outputs it in csv file
"""


"""
The code below creates a single columns list with names of each of the data point indexes

For each dep, we want to know various info like: name, version, author ....
the code below makes sure there is single structure for it

It might be a good idea to somehow imbed this info into data later on
"""
def createColumnName(name, version):
    return "{name}: {version}".format(name = name, version = version)

relavant_django = [1.11, 2.0, 2.1, 2.2]
relavant_python = [2.7, 3.5, 3.6, 3.7]
columns = ["Name", "Author", "Version", "Home-page", "Requires"]
for version in relavant_python:
    columns.append(createColumnName("Python", version))
for version in relavant_django:
    columns.append(createColumnName("Django", version))

columns_index_dict = { key: index for index, key in enumerate(columns)}

def create_data(parsed_details):
    """
    parsed_details: dict with various nesting that has info 
    This function converts dict to array
    """
    output = []
    for key in columns_index_dict:
        output.append(None)
    output[columns_index_dict["Name"]] = parsed_details["Name"]
    output[columns_index_dict["Author"]] = parsed_details["Author"]
    output[columns_index_dict["Version"]] = parsed_details["Version"]
    output[columns_index_dict["Home-page"]] = parsed_details["Home-page"]
    output[columns_index_dict["Requires"]] = ", ".join(parsed_details["Requires"])
    for version in relavant_python:
        name = createColumnName("Python", version)
        output[columns_index_dict[name]] = False
        if "Python" in parsed_details:
            if version in parsed_details["Python"]:
                output[columns_index_dict[name]] = True

    for version in relavant_django:
        name = createColumnName("Django", version)
        output[columns_index_dict[name]] = False
        if "Django" in parsed_details:
            if version in parsed_details["Django"]:
                output[columns_index_dict[name]] = True
    return output

def capitalize_key_names(dictionary):
    """Returns a new dict that has all the key names capitalized"""
    new_dict = {}
    for key in dictionary:
        new_dict[key.capitalize()] = dictionary[key]
    return new_dict


def get_list_dependencies():
    #Returns list of dictionaires: [{"version": "", "name": ""}]
    with open(os.devnull, 'w') as devnull:
        pip_list = check_output(['pip', 'list', '--format', 'json'],
                                stderr=devnull, universal_newlines=True)
        packages_temp = json.loads(pip_list)
        packages = {}
        for package in packages_temp:
            package = capitalize_key_names(package)
            packages[package["Name"]]=package
        return packages


def get_package_details_str(package_name, try_parsing = True):
    # runs pip show for given package
    with open(os.devnull, 'w') as devnull:
        details = check_output(['pip', 'show', '--verbose', package_name],
                               stderr=devnull, universal_newlines=True)
        return details


def parse_details_string(detail_string):
    """pip show --verbose returns a string with details on package
    string is formated in a sway readable by BytesHeaderParser
    this function takes a detail string and tries to parse as much data out of it as is possible
    """
    final_details = detail_string
    parsable_details = BytesHeaderParser().parsebytes(final_details.encode())
    temp_dict = dict(parsable_details.items())
    if not test_serializability(temp_dict):
        #something in dict is not serializable, figure it out
        for key in temp_dict:
            if not test_serializability({key: temp_dict[key]}):
                if isinstance(temp_dict[key], email.header.Header):
                    temp_dict[key] = str(temp_dict[key])
                else:
                    raise ValueError("Value not default serializable, please use pdb.set_trace to investigate")
    try:
        temp_classifier = parse_classifier(temp_dict["Classifiers"])
        temp_dict["Classifiers"] = temp_classifier
    except:
        temp_dict["Classifiers"] = {"value": temp_dict["Classifiers"]}
        None 
    temp_dict["Requires"] = [require.strip() for require in temp_dict["Requires"].split(",")]
    final_details = temp_dict
    return final_details


def parse_classifier(classifier):
    """
    the lines in classifiers in details are structured:
    value::value::value
    this function takes classifier straing and tries to read data out of it if possible
    """
    lines = classifier.splitlines()
    splits = []
    for line in lines:
        if "::" in line:
            split = [value.strip() for value in line.split("::")]
            splits.append(split)
    return convert_to_dict(splits)

def convert_to_dict(lists):
    """takes list of lists and tries to compress stackable data 
    into a dict(works only with one level nesting
    """
    if max([len(one_list) for one_list in lists]) == 1:
        output = []
        for one_list in lists:
            if len(one_list)>0:
                value = one_list[0]
                # if value can be converted to float do it
                try:
                    value = float(value)
                except ValueError:
                    value = one_list[0]
                output.append(value)
        if len(output)>1:
            return output
        else:
            return output[0]
    max_level = max([len(one_list) for one_list in lists])
    list_level = 0
    sorted_by_level_list = sorted(lists, key = lambda test_list: test_list[list_level])
    temp_dict = {}
    # Figure out which exist lots
    for one_list in sorted_by_level_list:
        # pdb.set_trace()
        if one_list[list_level] not in temp_dict.keys():
            temp_dict[one_list[list_level]] = [one_list[list_level+1:]]
        else:
            temp_dict[one_list[list_level]].append(one_list[list_level+1:])
    for key in temp_dict:
        temp_dict[key] = convert_to_dict(temp_dict[key])
    return temp_dict

def test_serializability(dict_input):
    """tests to see if dict input is serializable into json"""
    with open(os.devnull, 'w') as devnull:
        try:
            json.dump(dict_input, devnull)
        except:
            return False
        return True


def find_django_info_in_details(package):
    """ 
    check for django info in classifier
    """
    django_versions = []
    classifier = package["Classifiers"]
    if isinstance(classifier, dict) and "Framework" in classifier.keys():
        if isinstance(classifier["Framework"], dict) and "Django" in classifier["Framework"].keys():
            if isinstance(classifier["Framework"]["Django"], list):
                django_versions.extend(classifier["Framework"]["Django"])
            else:
                django_versions.append(classifier["Framework"]["Django"])
    #check if django_versions has something in it
    if not django_versions:
        # if not, check if Django is included in required
        for req_deps in package["Requires"]:
            # django can be captilized or not
            if "jango" in req_deps:
                django_versions = ["?"]
    return django_versions



def find_python_info_in_details(package):
        """ 
    check for python info in classifier
    """
    python_versions = []
    classifier = package["Classifiers"]
    if isinstance(classifier, dict) and "Programming Language" in classifier.keys():
        if isinstance(classifier["Programming Language"], dict) and "Python" in classifier["Programming Language"].keys():
            if isinstance(classifier["Programming Language"]["Python"],list):
                python_versions.extend(classifier["Programming Language"]["Python"])
            else:
                python_versions.append(classifier["Programming Language"]["Python"])
    return python_versions


def get_packages_details():
    """
    The function will call pip list to get list of all dependences installed in env.
    For each dependency, it will call pip show --verbose dependency and save returned string in packages
    returns packages dict={package name: {name:value, version: value, details: value}}
    """
    packages = get_list_dependencies()
    for package_name in tqdm(packages):
        details_str = get_package_details_str(package_name)
        packages[package_name]["details"] = details_str
    return packages


def parsing_out_info(packages):
    """
    packages= ={package name: {name:value, version: value, details: value}}
    the function parses through details for each package and outputs in data structure created
    at top of file
    """
    data = []
    for package_name in tqdm(packages):
        details_str = packages[package_name]["details"]
        parsed_details = parse_details_string(details_str)
        packages[package_name].update(parsed_details)
        packages[package_name]["Django"] = find_django_info_in_details(packages[package_name])
        packages[package_name]["Python"] = find_python_info_in_details(packages[package_name])
        data.append(create_data(packages[package_name]))
    return data



parser = argparse.ArgumentParser(
    description="Process and categorize pytest warnings and output html report."
)
parser.add_argument("--read_data_from_file", default=None)
parser.add_argument("--save_raw_data", default=None)
parser.add_argument("--csv_path", default="data.csv")
args = parser.parse_args()

packages = {}
if args.read_data_from_file==None:
    packages = get_packages_details()
    if args.save_raw_data !=None:
        with open(os.path.expanduser(args.save_raw_data),"w") as json_file:
            json.dump(packages, json_file)
else:
    with open(os.path.expanduser(args.read_data_from_file),"r") as json_file:
        packages = json.load(json_file)

data = parsing_out_info(packages)
info_dataframe = pd.DataFrame(data = data, columns=columns)
info_dataframe.to_csv(os.path.expanduser(args.csv_path))
        