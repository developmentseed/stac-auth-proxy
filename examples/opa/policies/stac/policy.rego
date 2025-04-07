package stac

default cql2 := "\"naip:year\" = 2021"

cql2 := "1=1" if {
	input.payload.sub != null
}
