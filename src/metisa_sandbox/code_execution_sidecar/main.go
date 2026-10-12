package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"time"

	"go.starlark.net/starlark"
)

func execute(code string) (string, error) {
	thread := &starlark.Thread{Name: "execute"}
	thread.SetMaxExecutionSteps(100_000)

	timer := time.AfterFunc(5*time.Second, func() {
		thread.Cancel("execution time limit exceeded")
	})
	defer timer.Stop()

	globals, err := starlark.ExecFile(thread, "agent.star", code, nil)
	if err != nil {
		return "", err
	}
	main, ok := globals["main"]
	if !ok {
		return "", fmt.Errorf("script must define main()")
	}
	value, err := starlark.Call(thread, main, nil, nil)
	if err != nil {
		return "", err
	}
	if text, ok := starlark.AsString(value); ok {
		return text, nil
	}
	return value.String(), nil
}

func handleExecute(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	var request struct {
		Code string `json:"code"`
	}

	const maxBodyBytes = 512 * 1024
	r.Body = http.MaxBytesReader(w, r.Body, maxBodyBytes)

	decoder := json.NewDecoder(r.Body)
	err := decoder.Decode(&request)
	if err == nil {
		// Require one JSON document and check the remaining body against the limit.
		var trailing any
		err = decoder.Decode(&trailing)
		if errors.Is(err, io.EOF) {
			err = nil
		} else if err == nil {
			err = fmt.Errorf("request body must contain exactly one JSON document")
		}
	}
	if err != nil {
		status := http.StatusBadRequest
		message := err.Error()

		var sizeError *http.MaxBytesError
		if errors.As(err, &sizeError) {
			status = http.StatusRequestEntityTooLarge
			message = "request body exceeds 512 KiB limit"
		}

		w.WriteHeader(status)
		json.NewEncoder(w).Encode(map[string]string{"error": message})
		return
	}

	const maxCodeBytes = 256 * 1024

	if len(request.Code) > maxCodeBytes {
		w.WriteHeader(http.StatusRequestEntityTooLarge)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "code exceeds 256 KiB limit",
		})
		return
	}

	result, err := execute(request.Code)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}
	json.NewEncoder(w).Encode(map[string]string{"result": result})
}

func checkHealth() error {
	client := &http.Client{Timeout: 2 * time.Second}
	response, err := client.Post(
		"http://127.0.0.1:8090/healthcheck",
		"application/json",
		nil,
	)
	if err != nil {
		return err
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("healthcheck returned HTTP %d", response.StatusCode)
	}
	return nil
}

func handleHealthcheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"result": "success"})
}

func main() {
	if len(os.Args) == 2 && os.Args[1] == "healthcheck" {
		if err := checkHealth(); err != nil {
			log.Fatal(err)
		}
		return
	}

	http.HandleFunc("POST /execute", handleExecute)
	http.HandleFunc("POST /healthcheck", handleHealthcheck)
	log.Fatal(http.ListenAndServe(":8090", nil))
}
