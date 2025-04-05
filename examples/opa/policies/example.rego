package example

# Helper function to check if user is authenticated
is_authenticated if {
    input.payload != null
}

# Return the list of permitted collections
collections = ["naip"] if {
    input.payload != null
} else = [] if {
    true
}

# Allow access to collections list - authenticated users see their permitted collections
allow if {
    input.method == "GET"
    input.path = ["collections"]
}
