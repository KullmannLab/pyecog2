import rsa
from base64 import b64encode, b64decode
import uuid
import json
from datetime import datetime
import os, sys
import pkg_resources
from shutil import copyfile


# Public key to verify license file signature
pubkey = rsa.PublicKey(16160501517992240089489846045349330669531152748177637683052739285650726050095013589498701009609073251511075671783463867319061107452539877753039298363106560208568640960646323319423025360553993833886655131296759508616091722165231946814978345933988965528254959018673373531918594327413336656397976939351525709525919579232842716368726978010250715238673016659338208384473234509831815005613006652353937286593354725850803186556509852812616829614815430879115963411874956492581567100421637278945823085398573094334807349492655017553426386461390694616597434456588704250875115154272458262326129077061504245567331427441737479463173, 65537)

# Keys to sign license log file
privkey_soft = rsa.PrivateKey(27423163235644346485133860236804449731398984821310866764558031511154981378499653780003094948565121612403171132511415458677887046315045637276901294643472964355901015099991465147402546845126316913071514248796631182242857289851573218225548603377652738877741089875144665763262962835350268693622400768538673655869615242668632196979743111545313005699842064195542482972837613077126580972028167737389677586018473339069678520871639428065159350264719948509110719059277086545482382885012293220320303067417282091990421104442141765615215275705780517959465517992237276053894270102278036881401844722622041062603388105013275995703791, 65537, 25964907229476524529586741770514208992367209456215296770898194475337426255377275681779026317169887640460222090034611777192734592641427161516491129212762018160922376504641201082237863143472820194545273695261128188970105139842681559078562368384120538822979234767115931457680293114716188915825628588944535234010818581268160325127592131723679594965495066720247781503137809257250557266577141467682179867234577440911605389136144821396099346903947138818999000627700328467806656277562731144996773888713487684993392965772718530451495168551534679703853372609719659469564617328220190256792779493685729479274988373198387696082625, 3110160118993296955043313309845643316886915663709412265047483492072717330202572097069277948426390646322538767242407374072252641424008766720408970062141053535860988814995856623445821644336819133542485805793278522644265776260085823301837845532417086596984934935560225348080604909764458544239415497224393008905308600235355216820087, 8817283415144790856429029955956960060061844937890731013848895884275704630631462563598083601960527266297423036911654001472229049515607108998386283178073341440784283724566928925024747413560900570973658153735888273596445869750000447049139861507863632407894485539437957597310584931618734821193)
pubkey_soft = rsa.PublicKey(27423163235644346485133860236804449731398984821310866764558031511154981378499653780003094948565121612403171132511415458677887046315045637276901294643472964355901015099991465147402546845126316913071514248796631182242857289851573218225548603377652738877741089875144665763262962835350268693622400768538673655869615242668632196979743111545313005699842064195542482972837613077126580972028167737389677586018473339069678520871639428065159350264719948509110719059277086545482382885012293220320303067417282091990421104442141765615215275705780517959465517992237276053894270102278036881401844722622041062603388105013275995703791, 65537)

def check_filepath_ID(fname,id):
    if os.name == 'posix':
        output = os.popen(fr"ls -i {fname}").read().split(' ')[0]
        return output == id
    else:
        output = os.popen(fr"fsutil file queryfileid {fname}").read().split(' ')[-1]
        return output == id


def get_filepath_ID(fname):
    if os.name == 'posix':
        return os.popen(fr"ls -i {fname}").read().split(' ')[0]
    else:
        return os.popen(fr"fsutil file queryfileid {fname}").read().split(' ')[-1]


def verify_license_file():
    fname = pkg_resources.resource_filename('pyecog2', 'license/PyEcogLicense.txt')
    with open(fname, 'r') as f:
        license_dict = json.load(f)

    # Verify signature:
    keys = ['user ID', 'expiry date', 'computer ID', 'license reg path', 'license reg ID']
    licensestring = ''.join([license_dict[k] for k in keys]).encode('utf-8')
    signature = license_dict['signature']
    try:
       rsa.verify(licensestring, b64decode(signature), pubkey)
       print('Valid license file: ', fname)
    except rsa.VerificationError:
        print('Invalid license file signature: ', fname)
        print(licensestring)
        print(signature)
        return False
    except:
        print(sys.exc_info())
        print(f'Error checking:{fname} signature')
        return False

    if license_dict['user ID'] == 'KullmannLab': # Consider asking to register computer IDs in the future if software spreads so to avoid "master Key" type of insecurities
        print('KullmannLab users do not need any further checks')
        return True

    # Check expiry date
    if datetime.strptime(license_dict['expiry date'],'%Y-%m-%d') < datetime.now():
        print('License expired')
        return False

    # Check clock has not been tampered with by verifying license reg file
    update_license_reg_file()
    if not verify_license_reg_file(license_dict['license reg path'], license_dict['license reg ID']):
        print('License reg file not valid:',license_dict['license reg path'])
        return False

    # Check if computer ID matches current ID
    if license_dict[ 'computer ID'] != str(hex(uuid.getnode())):
        print('License is registered to a different computer')
        return False

    # All checks passed
    return True


def verify_license_reg_file(filepath,fileid):
    if not check_filepath_ID(filepath,fileid):
        print('license_reg file ID does not match licensed ID')
        return False

    with open(filepath, 'r') as f:
        license_reg_dict = json.load(f)
        # Verify signature:
        licenseregstring = license_reg_dict['last date'].encode('utf-8')
        signature = b64decode(license_reg_dict['signature'])
        try:
            rsa.verify(licenseregstring, signature, pubkey_soft)
            print('Valid license file: ', filepath)
        except rsa.VerificationError:
            print('Invalid license file signature: ', filepath)
            return False
        except: # everything else needs to be captured an returned false
            print(sys.exc_info())
            print(f'Error checking:{filepath} signature')
            return False

    return True


def update_license_reg_file():
    filepath = pkg_resources.resource_filename('pyecog2', 'license/license_reg.txt')
    with open(filepath, 'r') as f:
        license_reg_dict = json.load(f)

    licenseregstring = license_reg_dict['last date'].encode('utf-8')
    signature = b64decode(license_reg_dict['signature'])

    try:
        rsa.verify(licenseregstring, signature, pubkey_soft)
        print('Valid license_reg file: ', filepath)
        signature_is_valid = True
    except rsa.VerificationError:
        print('Invalid license_reg file signature: ', filepath)
        return False
    except:
        print(sys.exc_info())
        print(f'Error checking:{filepath} signature')
        return False

    now = int(datetime.now().timestamp())
    if now >=  int(license_reg_dict['last date']) and signature_is_valid:
        license_reg_dict['last date'] = str(now)
        licenseregstring = license_reg_dict['last date'].encode('utf-8')
        signature =  rsa.sign(licenseregstring, privkey_soft, 'SHA-1')
        license_reg_dict['signature'] = b64encode(signature).decode('ascii')
    else:
        license_reg_dict['last date'] = 'Invalid: ' + str(now) + ' < ' + license_reg_dict['last date']
        license_reg_dict['signature'] = ''
        signature_is_valid = False

    with open(filepath, 'w') as f:
            json.dump(license_reg_dict,f)
    return signature_is_valid


def update_license_file():
    license_file_path = pkg_resources.resource_filename('pyecog2', 'license/PyEcogLicense.txt')
    with open(license_file_path, 'r') as f:
        license_dict = json.load(f)
    license_dict['license reg path'] = pkg_resources.resource_filename('pyecog2', 'license/license_reg.txt')
    license_dict['license reg ID'] = get_filepath_ID(license_dict['license reg path'])
    update_license_reg_file()
    license_dict['computer ID'] = str(hex(uuid.getnode()))
    with open(license_file_path, 'w') as f:
        json.dump(license_dict, f)

def copy_license_to_folder(filename):
    update_license_file()
    copyfile(pkg_resources.resource_filename('pyecog2', 'license/PyEcogLicense.txt'), filename)
    return filename

def copy_activated_license(fname):
    update_license_file()
    copyfile(fname, pkg_resources.resource_filename('pyecog2', 'license/PyEcogLicense.txt'))
    return fname + 'PyEcogLicense.txt'