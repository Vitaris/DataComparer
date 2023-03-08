import sys
import pandas as pd
import random

# get argument form arg vector
letter = sys.argv[1]


# create a DataFrame
file_01_old = pd.DataFrame(columns=['A', 'B', 'C', 'D', 'E'])
file_01_old = file_01_old.astype({'A': 'int32', 'B': 'int32', 'C': 'int32', 'D': 'int32', 'E': 'float'})
repeats = 100
row = 0

for i in range(0, repeats):
    for j in range(0, repeats):
        for k in range(0, 25):
            file_01_old.loc[row] = [i, j, k, random.randint(-100, 100), random.uniform(-10.0, 10.0)]
            k += 1
            row += 1
        j += 1
    i += 1
    print("iteration: " + str(i))

file_01_old = file_01_old.astype({'A': 'int32', 'B': 'int32', 'C': 'int32', 'D': 'int32', 'E': 'float'})
print("Casted to int and float")

file_01_new = file_01_old.sample(frac=1)
print("Shuffled")

# save files to csv, int will be saved as ints, float will be saved as floats
file_01_old.to_csv(f'files\\file_{letter}_old.csv', index=False, float_format='%.2f')
print("Saved file_01.csv")
file_01_new.to_csv(f'files\\file_{letter}_new.csv', index=False, float_format='%.2f')
