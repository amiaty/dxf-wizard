from pathlib import Path
import mimetypes
from time import time
import httpx

class Wistor:
    def __init__(self, repo:str, login:str, psw:str, viewer: str | None = None, cgi: str | None = None) -> None:
        self.repo = repo
        self.login = login
        self.psw = psw
        self.viewer_path = viewer
        self.session_x = httpx.Client(http2=True)
        self.cgi = cgi or 'https://app.wistor.nl/servlets/cgi/'
        self.repo_uri = f'{self.cgi}login/{self.repo}'
        self.rule_uri = f'{self.cgi}command/{self.repo}'
        self.download_uri = f'{self.cgi}download/{self.repo}/'
        self.query_uri =  f'{self.cgi}sparql/{self.repo}'
        self.upload_uri = f'{self.cgi}upload/{self.repo}'
        self.is_logged_in_uri = f'{self.cgi}isloggedin/{self.repo}?viewerPath={self.viewer_path}'
        self.start_session()

    def start_session(self) -> None:
        res_2 = self.session_x.post(self.repo_uri,json={"login":self.login,"psw":self.psw},timeout=10)
        print(res_2.json())

    def execute_rule(self, rule:str, parameters:dict|None, debug_mode:bool = False) -> dict | None:
        message = {
            "commando":"VRCommands",
            "command2":"runSparqlRulesWithTag",
            "command3":rule,
            "parameters":str(parameters),
            "debugMode": debug_mode
        }
        response = self.session_x.post(self.rule_uri,json=message, timeout=120)
        return response.json()
    
    def download_file(self, filename:str):
        response = self.session_x.get(f'{self.download_uri}{filename}',timeout=60)
        return response.content
    
    def query(self, query:str, infer:bool = False, same_as:bool = False) -> dict:
        message = {
            'infer': infer,
            'sameAs': same_as,
            'query': f'{query}#{time()}'
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = self.session_x.post(self.query_uri,data=message, headers=headers)
        return response.json()
    
    def download_last_file(
            self, 
            destination: str | None = None,
            graph: str = 'http://wistor.nl/upload/admin/uploadanyfile',
            ):

        query = f"""
                PREFIX file: <http://wistor.nl/upload/admin/uploadanyfile#>
                SELECT ?filename
                FROM <{graph}>
                WHERE {{
                    ?files a file:UploadedFile;
                        file:dateTime ?dateTime;
                        file:filename ?filename.
                }}
                ORDER BY DESC(?dateTime)
                LIMIT 1
        """
        answer = self.query(query)
        file_name = answer['results']['bindings'][0]['filename']['value']
        file = self.download_file(file_name)
        if destination:
            des_file = open(f'{destination}{Path(file_name).suffix}','wb')
            des_file.write(file)
            des_file.close()
        return file
    
    def upload_file(self, source: str, rule_tag:str | None = None, parameters: dict | None = None):
        if not parameters:
            parameters = {}
        parameters['command'] = rule_tag

        file = {'file':(Path(source).name, open(source, 'rb'), mimetypes.guess_type(source)[0])}
        
        response = self.session_x.post(self.upload_uri,data=parameters,files=file, timeout=6000)
        return response


    def is_logged_in(self):
        response = self.session_x.get(self.is_logged_in_uri)
        return response