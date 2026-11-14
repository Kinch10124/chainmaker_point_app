package main

import (
	"strconv"

	"chainmaker.org/chainmaker/contract-sdk-go/v2/pb/protogo"
	"chainmaker.org/chainmaker/contract-sdk-go/v2/sandbox"
	"chainmaker.org/chainmaker/contract-sdk-go/v2/sdk"
)

// SimpleContract 简化合约
type SimpleContract struct {
}

func main() {
	err := sandbox.Start(new(SimpleContract))
	if err != nil {
		sdk.Instance.Errorf(err.Error())
	}
}

// InitContract 合约初始化函数
func (c *SimpleContract) InitContract() protogo.Response {
	// 设置初始状态
	err := sdk.Instance.PutState("name", "", "积分通证")
	if err != nil {
		return sdk.Error("Failed to set name: " + err.Error())
	}
	err = sdk.Instance.PutState("symbol", "", "POINT")
	if err != nil {
		return sdk.Error("Failed to set symbol: " + err.Error())
	}
	err = sdk.Instance.PutState("decimals", "", "2")
	if err != nil {
		return sdk.Error("Failed to set decimals: " + err.Error())
	}
	err = sdk.Instance.PutState("totalSupply", "", "1000000")
	if err != nil {
		return sdk.Error("Failed to set totalSupply: " + err.Error())
	}
	// 设置管理员
	admin, err := sdk.Instance.Origin()
	if err != nil {
		return sdk.Error("Failed to get admin: " + err.Error())
	}
	err = sdk.Instance.PutState("admin", "", admin)
	if err != nil {
		return sdk.Error("Failed to set admin: " + err.Error())
	}
	// 给管理员初始余额
	err = sdk.Instance.PutState("balance", admin, "1000000")
	if err != nil {
		return sdk.Error("Failed to set initial balance: " + err.Error())
	}
	return sdk.Success([]byte("Simple contract initialized successfully"))
}

// UpgradeContract 合约升级函数
func (c *SimpleContract) UpgradeContract() protogo.Response {
	return sdk.Success([]byte("Simple contract upgraded successfully"))
}

// InvokeContract 合约调用入口函数
func (c *SimpleContract) InvokeContract(method string) protogo.Response {
	switch method {
	case "Name":
		name, err := sdk.Instance.GetState("name", "")
		if err != nil {
			return sdk.Error("Failed to get name: " + err.Error())
		}
		return sdk.Success([]byte(name))
	case "Symbol":
		symbol, err := sdk.Instance.GetState("symbol", "")
		if err != nil {
			return sdk.Error("Failed to get symbol: " + err.Error())
		}
		return sdk.Success([]byte(symbol))
	case "Decimals":
		decimals, err := sdk.Instance.GetState("decimals", "")
		if err != nil {
			return sdk.Error("Failed to get decimals: " + err.Error())
		}
		return sdk.Success([]byte(decimals))
	case "TotalSupply":
		totalSupply, err := sdk.Instance.GetState("totalSupply", "")
		if err != nil {
			return sdk.Error("Failed to get totalSupply: " + err.Error())
		}
		return sdk.Success([]byte(totalSupply))
	case "BalanceOf":
		args := sdk.Instance.GetArgs()
		account, ok := args["account"]
		if !ok {
			return sdk.Error("Missing account parameter")
		}
		balance, err := sdk.Instance.GetState("balance", string(account))
		if err != nil {
			return sdk.Success([]byte("0")) // 新账户返回0
		}
		return sdk.Success([]byte(balance))
	case "Transfer":
		args := sdk.Instance.GetArgs()
		from, ok := args["from"]
		if !ok {
			return sdk.Error("Missing from parameter")
		}
		to, ok := args["to"]
		if !ok {
			return sdk.Error("Missing to parameter")
		}
		amount, ok := args["amount"]
		if !ok {
			return sdk.Error("Missing amount parameter")
		}
		// 获取发送者余额
		fromBalance, err := sdk.Instance.GetState("balance", string(from))
		if err != nil {
			return sdk.Error("Failed to get sender balance: " + err.Error())
		}
		// 简单的余额检查（这里应该用更安全的数学运算）
		fromBalanceInt, _ := strconv.Atoi(fromBalance)
		amountInt, _ := strconv.Atoi(string(amount))
		if fromBalanceInt < amountInt {
			return sdk.Error("Insufficient balance")
		}
		// 更新发送者余额
		newFromBalance := strconv.Itoa(fromBalanceInt - amountInt)
		err = sdk.Instance.PutState("balance", string(from), newFromBalance)
		if err != nil {
			return sdk.Error("Failed to update sender balance: " + err.Error())
		}
		// 获取接收者余额
		toBalance, err := sdk.Instance.GetState("balance", string(to))
		if err != nil {
			toBalance = "0"
		}
		// 更新接收者余额
		toBalanceInt, _ := strconv.Atoi(toBalance)
		newToBalance := strconv.Itoa(toBalanceInt + amountInt)
		err = sdk.Instance.PutState("balance", string(to), newToBalance)
		if err != nil {
			return sdk.Error("Failed to update receiver balance: " + err.Error())
		}
		// 触发转账事件
		sdk.Instance.EmitEvent("Transfer", []string{string(from), string(to), string(amount)})
		return sdk.Success([]byte("Transfer successful"))
	case "Mint":
		args := sdk.Instance.GetArgs()
		account, ok := args["account"]
		if !ok {
			return sdk.Error("Missing account parameter")
		}
		amount, ok := args["amount"]
		if !ok {
			return sdk.Error("Missing amount parameter")
		}
		// 检查权限
		sender, err := sdk.Instance.Sender()
		if err != nil {
			return sdk.Error("Failed to get sender: " + err.Error())
		}
		admin, err := sdk.Instance.GetState("admin", "")
		if err != nil {
			return sdk.Error("Failed to get admin: " + err.Error())
		}
		if sender != admin {
			return sdk.Error("Only admin can mint tokens")
		}
		// 获取当前余额
		currentBalance, err := sdk.Instance.GetState("balance", string(account))
		if err != nil {
			currentBalance = "0"
		}
		// 更新余额
		currentBalanceInt, _ := strconv.Atoi(currentBalance)
		amountInt, _ := strconv.Atoi(string(amount))
		newBalance := strconv.Itoa(currentBalanceInt + amountInt)
		err = sdk.Instance.PutState("balance", string(account), newBalance)
		if err != nil {
			return sdk.Error("Failed to update balance: " + err.Error())
		}
		// 更新总供应量
		totalSupply, err := sdk.Instance.GetState("totalSupply", "")
		if err != nil {
			return sdk.Error("Failed to get totalSupply: " + err.Error())
		}
		totalSupplyInt, _ := strconv.Atoi(totalSupply)
		newTotalSupply := strconv.Itoa(totalSupplyInt + amountInt)
		err = sdk.Instance.PutState("totalSupply", "", newTotalSupply)
		if err != nil {
			return sdk.Error("Failed to update totalSupply: " + err.Error())
		}
		// 触发铸造事件
		sdk.Instance.EmitEvent("Mint", []string{string(account), string(amount)})
		return sdk.Success([]byte("Mint successful"))
	default:
		return sdk.Error("Unknown method: " + method)
	}
}
