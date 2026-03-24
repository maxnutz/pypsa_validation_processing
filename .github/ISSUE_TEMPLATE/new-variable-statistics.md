---
name: New Variable Statistics
about: Opens an issue for a new statistics-fuction in statistics_functions.py
title: 'New Variable Statistics: <variable_name>'
labels: ''
assignees: ''

---

### Goal: 
**Add a new function to extract the statistics of variable <variable_name>***

### To Dos:
- [ ] Create a new branch linked to this issue
- [ ] Write your pypsa-statistics and add it as a separate function to [statistics_functions.py](https://github.com/maxnutz/pypsa_validation_processing/blob/main/pypsa_validation_processing/statistics_functions.py) (please note the [naming and structural conventions](https://github.com/maxnutz/pypsa_validation_processing/tree/main#variables-statistics---functions)!)
- [ ] add a comprehensive docstring to your function 
- [ ] add the mapping variable_name <> function_name to [mapping.default.yaml](https://github.com/maxnutz/pypsa_validation_processing/blob/main/pypsa_validation_processing/configs/config.default.yaml) (and your personal mapping-file)
- [ ] Add a testing routine for your Function to `tests/` - stick to the [testing-README](https://github.com/maxnutz/pypsa_validation_processing/blob/main/tests/README.md)
- [ ] make sure, that the newest version of main is merged into your feature Branch 
- [ ] open a pull request and assign @maxnutz as reviewer
