package stac

default items_cql2 := "\"naip:year\" = 2021"

items_cql2 := "1=1" if {
	input.payload.sub != null
}

default collections_cql2 := "id = 'naip'"

collections_cql2 := "1=1" if {
	input.payload.sub != null
}
