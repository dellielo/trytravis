from kahelo import kahelo
 
def ma_fonction_a_tester(a, b):
    return (a * 2, b * 2)
 
 
def test_function():    
    print("youpi")
    # assert ma_fonction_a_tester(1, 1) == (2, 2)
    server = kahelo.HTTPServerLayer()
    server.port = 1028 # travis (or linux) block the port is less than 1024
    server.start_server("tests/easter.db")
    server.stop_server()
    print("stooooooooop")
    assert ma_fonction_a_tester(1, 1) == (2, 2)

if __name__ == '__main__':
    test_function()
