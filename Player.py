class Player:
    id = 0
    name_brief = ''
    first_name = ''
    last_name = ''
    position = ''
    age = 0
    average_position_age_diff = 0

    def __init__(self, id, first_name, last_name, position, age):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.position = position
        self.age = age

    def displayPlayer(self):
        print("ID:", self.id , ",First Name:", self.first_name, ",Last Name:",
              self.last_name, ",Position:",self.position,", Age: ", self.age)