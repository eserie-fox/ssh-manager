import re
from typing import List, Tuple
from ssh_manager.ssh_config.builder import SSHHostConfig

# Define token types.
TOKEN_TYPES = {
    "COMMENT": r"#.*",  # Comment (starts with #)
    "HOST": r"\bHost\b",  # Host name or wildcard (Host)
    "ITEM": r"\S+",  # Config item value
    "WHITESPACE": r"\s+",  # Whitespace
}


class SSHConfigLexer:
    def __init__(self, source_code):
        self.source_code = source_code
        self.tokens = []
        self.position = 0  # Current character index
        self.line = 1  # Current line number
        self.column = 1  # Current column number

    def get_token(self):
        """
        Get the next token and update line/column counters.
        """
        if self.position >= len(self.source_code):
            return None  # End of file

        for token_type, pattern in TOKEN_TYPES.items():
            regex = re.compile(pattern)
            match = regex.match(self.source_code, self.position)
            if match:
                value = match.group(0)
                self.position = match.end()  # Update current position

                # Update line and column
                lines = value.split("\n")  # Split into lines
                if len(lines) > 1:
                    # Multi-line token
                    self.line += len(lines) - 1  # Increment line count
                    self.column = len(lines[-1]) + 1  # New line column starts at 1
                else:
                    self.column += len(value)  # Increment column on current line

                # Skip whitespace tokens
                if token_type != "WHITESPACE":
                    return (token_type, value, self.line, self.column)

                # Recurse to skip whitespace
                return self.get_token()

        raise ValueError(
            f"Unexpected character at position {self.position} (Line {self.line}, Column {self.column})"
        )


class SSHConfigParser:
    def __init__(self, lexer):
        self.lexer = lexer
        self.current_token = None
        self.next_token = None
        self.get_next_token()
        self.get_next_token()

    def get_next_token(self):
        self.current_token = self.next_token
        self.next_token = self.lexer.get_token()
        return self.current_token

    def parse_host_head(self) -> str:
        if self.current_token is None:
            raise ValueError(f"Expected 'host', but got None")
        if self.current_token[0] != "HOST":
            raise ValueError(
                f"Expected 'host', but got {self.current_token[0]} at line {self.current_token[2]}, column {self.current_token[3]}"
            )
        self.get_next_token()
        if self.current_token is None:
            raise ValueError(f"Expected host name, but got None")
        if self.current_token[0] != "ITEM":
            raise ValueError(
                f"Expected host name, but got {self.current_token[0]} at line {self.current_token[2]}, column {self.current_token[3]}"
            )
        ret = self.current_token[1]
        self.get_next_token()
        return ret

    def parse_kv(self) -> Tuple[str, str]:
        if self.current_token is None:
            raise ValueError(f"Expected key, but got None")
        if self.next_token is None:
            raise ValueError(f"Expected value, but got None")
        if self.current_token[0] != "ITEM":
            raise ValueError(
                f"Expected key, but got {self.current_token[0]} at line {self.current_token[2]}, column {self.current_token[3]}"
            )
        if self.next_token[0] != "ITEM":
            raise ValueError(
                f"Expected value, but got {self.next_token[0]} at line {self.next_token[2]}, column {self.next_token[3]}"
            )
        ret = (self.current_token[1], self.next_token[1])
        self.get_next_token()
        self.get_next_token()
        return ret

    def parse_host_config(self) -> SSHHostConfig:
        host_comment = ""
        while True:
            if self.current_token is None:
                raise ValueError(f"Expected host config, but got None")
            if self.current_token[0] == "COMMENT":
                host_comment += self.current_token[1][1:] + " "
                self.get_next_token()
                continue
            break
        if self.current_token[0] != "HOST":
            raise ValueError(
                f"Expected host config, but got {self.current_token[0]} at line {self.current_token[2]}, column {self.current_token[3]}"
            )
        host_name = self.parse_host_head()
        host_config = SSHHostConfig(host_name, host_comment)
        comment = ""
        while True:
            if self.current_token is None:
                break
            if self.current_token[0] == "COMMENT":
                comment += self.current_token[1][1:] + " "
                self.get_next_token()
                continue
            if self.current_token[0] == "HOST":
                break
            key, value = self.parse_kv()
            host_config.add_config(key, value, comment)
            comment = ""

        return host_config

    def parse(self) -> List[SSHHostConfig]:
        ret = []
        while True:
            if self.current_token is None:
                break
            if self.current_token[0] == "COMMENT" and self.current_token[1] == "# This file is managed by ssh_manager":
                self.get_next_token()
                continue
            ret.append(self.parse_host_config())
        return ret


def parse_ssh_config(ssh_config_content: str) -> List[SSHHostConfig]:
    lexer = SSHConfigLexer(ssh_config_content)
    parser = SSHConfigParser(lexer)
    return parser.parse()
