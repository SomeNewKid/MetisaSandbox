package main

import (
	"fmt"
	"net/http"
	"os"
	"time"
)

func main() {
	client := &http.Client{
		Timeout: 2 * time.Second,
		Transport: &http.Transport{
			Proxy: nil,
		},
		CheckRedirect: func(
			request *http.Request,
			previous []*http.Request,
		) error {
			return http.ErrUseLastResponse
		},
	}

	response, err := client.Get("http://127.0.0.1:13133/")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	response.Body.Close()

	if response.StatusCode != http.StatusOK {
		fmt.Fprintln(os.Stderr, "Unexpected HTTP status:", response.Status)
		os.Exit(1)
	}
}