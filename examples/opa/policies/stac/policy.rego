package stac

default cql2 := "private = true"

cql2 := "1=1" if {
	input.payload.sub != null
}
