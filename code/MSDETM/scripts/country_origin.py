####Open csv file#####
####Read source (link) as the input from domain names####

####Get the country code from the domain####
import socket
from geolite2 import geolite2
import pandas as pd 
from tqdm import tqdm

array_country = []

#Get csv file
df = pd.read_csv("who_all.csv")

def origin(ip, domain_str, result):
    origin_country = "{0} [{1}]: {2}".format(domain_str.strip(), ip, result)
    #print(origin_country)
    #Add to array
    array_country.append(str(result))


def getip(domain_str):
    ip = socket.gethostbyname(domain_str.strip())
    reader = geolite2.reader()      
    output = reader.get(ip)
    result = output['country']['iso_code']
    origin(ip, domain_str, result)

ins = df["LINK"].tolist()
for domain_str in tqdm(ins):
    try:
        domain = str(domain_str)
        char40 = domain[0:40]
        strip_char = '/'
        char40 = strip_char.join(char40.split(strip_char)[:3])
        char40 = char40[char40.find('www'):]
        try:
            getip(char40)
        except:
            array_country.append(' ')
            continue
    except socket.error as msg:
        array_country.append(' ')
        #print("{0} [could not resolve]".format(char40.strip())) 
        if len(char40) > 2:
            try:
                subdomain = char40.split('.', 1)[1]
            except:
                continue
            try:
                getip(subdomain)
            except:
                continue

#Array to csv column : 
mapping = dict(enumerate(array_country))
df_new = pd.DataFrame(array_country, columns=["C_Origin"])
df_new.to_csv("who_country_origin.csv", index=False)

geolite2.close()

